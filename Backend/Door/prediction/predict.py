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
import sys
from pathlib import Path

import pandas as pd

from core.classifier import MODEL_PATH, DoorClassifier
from core.data import (
    CLOSE_CMD, CURRENT, EMF, OPEN_CMD, POSITION, TIME, VOLTAGE,
    find_cycles, parse_times, read_raw,
)
from core.features import build_table
from core.scoring import ABNORMAL, NORMAL, format_time

REQUIRED_COLUMNS = [TIME, CURRENT, VOLTAGE, EMF, POSITION, OPEN_CMD, CLOSE_CMD]


def check_schema(frame: pd.DataFrame) -> None:
    """Fail early and legibly if the input isn't a door stream."""
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SystemExit(
            "Input file is missing required column(s):\n"
            + "".join(f"  - {c}\n" for c in missing)
            + "\nFound these columns instead:\n"
            + "".join(f"  - {c}\n" for c in frame.columns)
            + "\nExpected a Door subsystem stream in the format of Train.csv/Test.csv."
        )
    if frame.empty:
        raise SystemExit("Input file contains no data rows.")


def predict_stream(
    frame: pd.DataFrame, classifier: DoorClassifier
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Segment and classify a stream.

    Returns the submission table and a per-cycle detail table for the app.
    """
    cycles = find_cycles(frame)
    if not cycles:
        return (
            pd.DataFrame(columns=["start_time", "end_time", "prediction"]),
            pd.DataFrame(),
        )
    table = build_table(frame, cycles)
    detail = classifier.explain(table)

    submission = pd.DataFrame({
        "start_time": [format_time(t) for t in detail["start_time"]],
        "end_time": [format_time(t) for t in detail["end_time"]],
        "prediction": detail["prediction"],
    })
    return submission, detail


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
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    model_path = Path(args.model)
    if not model_path.exists():
        raise SystemExit(
            f"Model file not found: {model_path}\n"
            "Run train.py first to fit the model."
        )

    classifier = DoorClassifier.load(model_path)

    try:
        frame = read_raw(input_path)
    except Exception as exc:  # malformed CSV, wrong encoding, not a CSV at all
        raise SystemExit(f"Could not read '{input_path}' as a CSV file: {exc}")

    check_schema(frame)  # validate before parsing, so errors stay readable

    try:
        frame = parse_times(frame)
    except ValueError as exc:
        raise SystemExit(str(exc))

    submission, detail = predict_stream(frame, classifier)

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
