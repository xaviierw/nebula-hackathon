"""Door subsystem inference: continuous stream in, predicted segments out.

Usage:
    python predict.py --input Test.csv --output door_predictions.csv

Reads one continuous door-controller stream, finds every open/close cycle in
it, classifies each as Normal or Abnormal resistance, and writes one row per
predicted segment in the submission schema.

Requires only numpy and pandas -- no scikit-learn -- so it runs anywhere,
including under Windows Smart App Control. scikit-learn was used during
training for model selection only (see train.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from core.classifier import MODEL_PATH, DoorClassifier
from core.data import (
    CLOSE_CMD, CURRENT, EMF, OPEN_CMD, POSITION, TIME, VOLTAGE,
    derive_gap_seconds, find_cycles, parse_times, read_raw,
)
from core.errors import DoorInputError, DoorModelError
from core.features import build_table
from core.scoring import ABNORMAL, NORMAL, format_time

REQUIRED_COLUMNS = [TIME, CURRENT, VOLTAGE, EMF, POSITION, OPEN_CMD, CLOSE_CMD]

# Written by training/train.py; absent only if the model predates it.
REFERENCE_PATH = MODEL_PATH.parent / "door_reference.json"

# A sampling interval within this relative tolerance of the fitted one is not
# worth warning about; clock jitter of a sample or two is normal.
INTERVAL_TOLERANCE = 0.05


def warn(code: str, severity: str, message: str, **extra) -> dict:
    """One structured warning.

    Warnings never block a prediction -- the caller gets the result AND the
    caveat, and decides what to show. Shape is documented in Backend/README.md.
    """
    return {"code": code, "severity": severity, "message": message, **extra}


def load_reference(path: Path = REFERENCE_PATH) -> dict | None:
    """Training-time facts about Train.csv. None if not exported yet."""
    if not Path(path).exists():
        return None
    try:
        return json.loads(Path(path).read_text())
    except (ValueError, OSError):
        return None


def check_sampling(frame: pd.DataFrame, reference: dict | None) -> list[dict]:
    """Flag a stream sampled at a different rate than the model was fitted on.

    Segmentation adapts (the gap threshold is derived per stream), but the
    features are not rate-invariant: a coarser stream shifts current_mid_mean,
    which is what the decision is made on. Prediction still runs -- the caller
    is told the result is less trustworthy, not denied it.
    """
    if reference is None or len(frame) < 2:
        return []
    fitted = float(reference.get("sampling_interval_seconds", 0.0))
    if fitted <= 0:
        return []
    observed = frame[TIME].diff().dt.total_seconds()
    observed = observed[observed <= derive_gap_seconds(frame)]
    if observed.empty:
        return []
    actual = float(observed.mode().iloc[0])
    if abs(actual - fitted) <= INTERVAL_TOLERANCE * fitted:
        return []
    return [warn(
        "sampling_interval",
        "warning",
        f"This file is sampled every {actual * 1000:.0f} ms, but the model was "
        f"fitted on {fitted * 1000:.0f} ms data. Cycles were still detected, but "
        f"the current measurements they are judged on shift with sampling rate, "
        f"so treat borderline results with caution.",
        observed_seconds=actual,
        expected_seconds=fitted,
    )]


def check_durations(detail: pd.DataFrame, reference: dict | None) -> list[dict]:
    """Flag segments outside the duration envelope seen in training.

    Catches a truncated file, whose final cycle is cut short and would otherwise
    be emitted as a complete segment with no indication anything is wrong.
    """
    if reference is None or detail.empty:
        return []
    bounds = reference.get("durations") or {}
    if not bounds:
        return []
    warnings = []
    for operation, limits in bounds.items():
        rows = detail[detail["operation"] == operation]
        if rows.empty:
            continue
        seconds = (rows["end_time"] - rows["start_time"]).dt.total_seconds()
        odd = rows[(seconds < limits["min"]) | (seconds > limits["max"])]
        if odd.empty:
            continue
        odd_seconds = (odd["end_time"] - odd["start_time"]).dt.total_seconds()
        # A cycle at less than half the training minimum is almost certainly a
        # recording cut off mid-cycle. Anything else is a real cycle that simply
        # ran a little long or short, which is worth noting but not alarming --
        # so don't tell the user their file is truncated when it isn't.
        truncated = odd_seconds[odd_seconds < 0.5 * limits["min"]]
        if len(truncated):
            explanation = (
                f" {len(truncated)} of them last under "
                f"{0.5 * limits['min']:.2f} s, which usually means the recording "
                f"was cut off mid-cycle."
            )
            severity = "warning"
        else:
            explanation = (
                " They are complete cycles that ran slightly outside the usual "
                "range, so the result is still meaningful -- but they are less "
                "like anything the model was fitted on."
            )
            severity = "info"
        warnings.append(warn(
            "segment_duration",
            severity,
            f"{len(odd)} {operation} cycle(s) fall outside the "
            f"{limits['min']:.2f}-{limits['max']:.2f} s range seen in training "
            f"(observed {odd_seconds.min():.2f}-{odd_seconds.max():.2f} s)."
            + explanation,
            operation=operation,
            n_segments=int(len(odd)),
            n_truncated=int(len(truncated)),
            expected_min=limits["min"],
            expected_max=limits["max"],
            observed=[round(v, 3) for v in odd_seconds.tolist()],
            start_times=[format_time(t) for t in odd["start_time"]],
        ))
    return warnings


def check_schema(frame: pd.DataFrame) -> None:
    """Fail early and legibly if the input isn't a door stream."""
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise DoorInputError(
            "Input file is missing required column(s):\n"
            + "".join(f"  - {c}\n" for c in missing)
            + "\nFound these columns instead:\n"
            + "".join(f"  - {c}\n" for c in frame.columns)
            + "\nExpected a Door subsystem stream in the format of Train.csv/Test.csv."
        )
    if frame.empty:
        raise DoorInputError("Input file contains no data rows.")


def predict_stream(
    frame: pd.DataFrame,
    classifier: DoorClassifier,
    reference: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict]]:
    """Segment and classify a stream.

    Returns four things:
      submission  the three-column table that becomes door_predictions.csv
      detail      one row per cycle: times, row indices, current, threshold,
                  verdict and margin -- what a UI shows
      features    the full feature table, every column build_table computes
      warnings    structured, non-blocking caveats (see Backend/README.md)

    `reference` is the training-time export; pass None to skip the guards.
    """
    empty_submission = pd.DataFrame(columns=["start_time", "end_time", "prediction"])
    cycles = find_cycles(frame)
    if not cycles:
        return empty_submission, pd.DataFrame(), pd.DataFrame(), []

    table = build_table(frame, cycles)
    detail = classifier.explain(table)

    submission = pd.DataFrame({
        "start_time": [format_time(t) for t in detail["start_time"]],
        "end_time": [format_time(t) for t in detail["end_time"]],
        "prediction": detail["prediction"],
    })
    warnings = check_sampling(frame, reference) + check_durations(detail, reference)
    return submission, detail, table, warnings


def load_inputs(
    input_path: Path, model_path: Path = MODEL_PATH
) -> tuple[DoorClassifier, pd.DataFrame]:
    """Read and validate a stream and the model, raising catchable errors.

    Every failure here is a DoorInputError or DoorModelError, never SystemExit,
    so a UI can show the message instead of having the process exit underneath
    it. predict.py's main() catches them and exits 1 with the same text.
    """
    if not input_path.exists():
        raise DoorInputError(f"Input file not found: {input_path}")
    if not model_path.exists():
        raise DoorModelError(
            f"Model file not found: {model_path}\n"
            "Run train.py first to fit the model."
        )
    classifier = DoorClassifier.load(model_path)
    try:
        frame = read_raw(input_path)
    except Exception as exc:  # malformed CSV, wrong encoding, not a CSV at all
        raise DoorInputError(
            f"Could not read '{input_path}' as a CSV file: {exc}"
        ) from exc

    check_schema(frame)  # validate before parsing, so errors stay readable

    try:
        frame = parse_times(frame)
    except ValueError as exc:
        raise DoorInputError(str(exc)) from exc
    return classifier, frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect and classify door open/close cycles in a continuous stream.",
    )
    parser.add_argument("--input", required=True,
                        help="continuous door stream CSV (e.g. Test.csv)")
    parser.add_argument("--output", required=True,
                        help="destination CSV, one row per predicted segment")
    parser.add_argument("--model", default=str(MODEL_PATH),
                        help="trained model JSON (default: model/door_model.json)")
    parser.add_argument("--detail", default=None,
                        help="optional CSV with per-cycle currents and thresholds")
    parser.add_argument("--quiet", action="store_true", help="suppress the summary")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    try:
        classifier, frame = load_inputs(input_path, Path(args.model))
    except (DoorInputError, DoorModelError) as exc:
        # Same message and same exit code the CLI has always produced; the only
        # difference is that an embedding caller can catch these instead.
        print(exc, file=sys.stderr)
        return 1

    submission, detail, _features, warnings = predict_stream(
        frame, classifier, load_reference()
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    submission.to_csv(output_path, index=False)

    if args.detail:
        detail_path = Path(args.detail)
        detail_out = detail.copy()
        detail_out["start_time"] = [format_time(t) for t in detail["start_time"]]
        detail_out["end_time"] = [format_time(t) for t in detail["end_time"]]
        detail_out.to_csv(detail_path, index=False)

    if not args.quiet:
        n_abnormal = int((submission["prediction"] == ABNORMAL).sum())
        n_normal = int((submission["prediction"] == NORMAL).sum())
        print(f"Input:   {input_path}  ({len(frame)} rows)")
        print(f"Cycles:  {len(submission)} detected")
        print(f"         {n_normal} Normal, {n_abnormal} Abnormal resistance")
        if len(submission):
            span = f"{submission['start_time'].iloc[0]} .. {submission['end_time'].iloc[-1]}"
            print(f"Span:    {span}")
        print(f"Output:  {output_path}")
        if args.detail:
            print(f"Detail:  {args.detail}")
        for item in warnings:
            print(file=sys.stderr)
            print(f"[{item['severity']}] {item['message']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
