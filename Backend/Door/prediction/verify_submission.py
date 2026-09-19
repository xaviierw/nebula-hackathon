"""Validate a door_predictions.csv before submitting it.

Checks the file against the schema in 04_Example_Submission/ and against the
rules in the info kit -- column names, label spelling, timestamp format, and
segment sanity. The example file's *values* are illustrative placeholders, so
only its structure is compared, never its contents.

Usage:
    python verify_submission.py --file door_predictions.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from core.data import DATA_DIR
from core.scoring import ABNORMAL, NORMAL, parse_time

EXAMPLE = DATA_DIR.parents[1] / "04_Example_Submission" / "door_predictions.csv"
REQUIRED = ["start_time", "end_time", "prediction"]
VALID_LABELS = {NORMAL, ABNORMAL}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)
        print(f"  FAIL  {message}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"  WARN  {message}")

    def ok(self, message: str) -> None:
        print(f"  ok    {message}")


def verify(path: Path) -> Report:
    report = Report()
    frame = pd.read_csv(path)

    print(f"Verifying {path}  ({len(frame)} rows)\n")

    # --- columns ------------------------------------------------------------
    print("Schema")
    columns = list(frame.columns)
    if columns[: len(REQUIRED)] == REQUIRED:
        report.ok(f"columns are {REQUIRED}")
    elif set(REQUIRED).issubset(columns):
        report.warn(f"columns present but ordered as {columns}; expected {REQUIRED} first")
    else:
        report.error(f"expected columns {REQUIRED}, found {columns}")
        return report

    extra = [c for c in columns if c not in REQUIRED]
    if extra == ["confidence"]:
        report.ok("extra 'confidence' column is explicitly allowed by the info kit")
    elif extra:
        report.warn(f"extra column(s) {extra} will be ignored by the scorer")

    if "file_id" in columns:
        report.error("'file_id' must NOT be present for Door -- Test is one continuous stream")

    if EXAMPLE.exists():
        example_columns = list(pd.read_csv(EXAMPLE).columns)
        if columns[: len(example_columns)] == example_columns:
            report.ok(f"matches the example submission's schema {example_columns}")
        else:
            report.error(f"schema {columns} differs from the example's {example_columns}")

    # --- content ------------------------------------------------------------
    print("\nContent")
    if frame.empty:
        report.error("file has no rows -- a submission with zero segments scores 0")
        return report

    if frame[REQUIRED].isna().any().any():
        report.error("found empty cells in required columns")

    labels = set(frame["prediction"].dropna().unique())
    bad_labels = labels - VALID_LABELS
    if bad_labels:
        report.error(
            f"invalid label(s) {sorted(bad_labels)}; "
            f"only {sorted(VALID_LABELS)} can match (exact spelling and case)"
        )
    else:
        report.ok(f"labels valid: {sorted(labels)}")

    n_abnormal = int((frame["prediction"] == ABNORMAL).sum())
    share = n_abnormal / len(frame)
    print(f"        {len(frame) - n_abnormal} Normal, {n_abnormal} Abnormal "
          f"({share:.0%} abnormal)")
    # Training ran at 27% abnormal; a wildly different rate suggests the
    # thresholds have not transferred to this stream.
    if not 0.05 <= share <= 0.60:
        report.warn(
            f"abnormal rate {share:.0%} is far from the ~27% seen in training -- "
            "worth checking whether the current distribution has shifted"
        )

    # --- timestamps ---------------------------------------------------------
    print("\nTimestamps")
    try:
        starts = [parse_time(v) for v in frame["start_time"]]
        ends = [parse_time(v) for v in frame["end_time"]]
        report.ok("all timestamps parse")
    except Exception as exc:
        report.error(f"could not parse timestamps: {exc}")
        return report

    non_positive = [i for i, (s, e) in enumerate(zip(starts, ends)) if e <= s]
    if non_positive:
        report.error(f"{len(non_positive)} segment(s) have end <= start "
                     f"(first at row {non_positive[0] + 2}) -- these score 0")
    else:
        report.ok("every segment has end > start")

    durations = [(e - s).total_seconds() for s, e in zip(starts, ends)]
    print(f"        durations {min(durations):.2f}s .. {max(durations):.2f}s "
          f"(training cycles ran 2.72s .. 3.78s)")
    odd = [d for d in durations if not 1.0 <= d <= 8.0]
    if odd:
        report.warn(f"{len(odd)} segment(s) outside 1-8s; a door cycle is ~3s")

    order = sorted(range(len(starts)), key=lambda i: starts[i])
    if order != list(range(len(starts))):
        report.warn("rows are not in chronological order (scoring still works)")
    else:
        report.ok("rows are in chronological order")

    overlaps = sum(
        1 for i in range(len(order) - 1)
        if ends[order[i]] > starts[order[i + 1]]
    )
    if overlaps:
        report.warn(f"{overlaps} pair(s) of segments overlap in time -- "
                    "real door cycles do not, so this may indicate over-segmentation")
    else:
        report.ok("no overlapping segments")

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a door_predictions.csv.")
    parser.add_argument("--file", required=True, help="the predictions CSV to check")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    report = verify(path)

    print("\n" + "=" * 60)
    if report.errors:
        print(f"NOT READY -- {len(report.errors)} error(s) must be fixed")
        for message in report.errors:
            print(f"  - {message}")
        return 1
    if report.warnings:
        print(f"VALID, with {len(report.warnings)} warning(s) to review:")
        for message in report.warnings:
            print(f"  - {message}")
        return 0
    print("VALID -- schema and content checks all passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
