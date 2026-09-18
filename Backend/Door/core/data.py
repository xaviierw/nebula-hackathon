"""Loading the continuous door stream, cutting it into cycles, and splitting it.

The stream is sampled at a rigid 20 ms *within* a door cycle, with long
irregular idle gaps (tens of seconds) between cycles. Cycle boundaries are
therefore breaks in sampling continuity, not transitions of the opening/closing
flags -- which is what the info kit's Section 2.2 note is pointing at.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.scoring import Segment, parse_time

# Column names as they appear in the CSV header.
TIME = "Datetime"
CURRENT = "Motor current(mA)"
VOLTAGE = "Motor Voltage(10mV)"
EMF = "Motor electrodynamic force"
POSITION = "Door leaf position"
OPEN_CMD = "Open command"
CLOSE_CMD = "Close command"

# Intra-cycle sampling period is 20 ms; inter-cycle gaps are 20-55 s. Any
# threshold in that enormous range yields identical segmentation, so this is a
# structural constant rather than a tuned hyperparameter.
GAP_SECONDS = 0.1

DATA_DIR = Path(__file__).resolve().parents[2] / "02_Datasets" / "Door"


def read_raw(path: str | Path) -> pd.DataFrame:
    """Read a stream CSV without touching its contents.

    Kept separate from timestamp parsing so a caller can validate the schema
    first and report a readable error, rather than failing inside the parser on
    a file that was never a door stream to begin with.
    """
    return pd.read_csv(path)


def parse_times(frame: pd.DataFrame) -> pd.DataFrame:
    """Parse the timestamp column of an already-validated stream."""
    frame = frame.copy()
    try:
        frame[TIME] = [parse_time(v) for v in frame[TIME]]
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Could not parse the '{TIME}' column as timestamps. Expected the "
            f"dataset's native Year-Month-Date-Hour-Minute-Second-Millisecond "
            f"format (e.g. 2023-7-5-0-11-17-664) or an ISO timestamp. ({exc})"
        ) from exc
    return frame


def load_stream(path: str | Path) -> pd.DataFrame:
    """Read a continuous stream CSV with its timestamp column parsed."""
    return parse_times(read_raw(path))


def load_truth(path: str | Path) -> list[Segment]:
    """Read Train_Segments_Answer.csv into scorer Segments."""
    frame = pd.read_csv(path)
    return [
        Segment(parse_time(row.start_time), parse_time(row.end_time), row.status)
        for row in frame.itertuples()
    ]


def load_truth_frame(path: str | Path) -> pd.DataFrame:
    """Read the answer file keeping every column (operation, n_rows, ...)."""
    frame = pd.read_csv(path)
    frame["start_time"] = [parse_time(v) for v in frame["start_time"]]
    frame["end_time"] = [parse_time(v) for v in frame["end_time"]]
    return frame


def find_cycles(frame: pd.DataFrame, gap_seconds: float = GAP_SECONDS) -> list[tuple[int, int]]:
    """Split the stream into cycles at breaks in sampling continuity.

    Returns inclusive ``(start_row, end_row)`` index pairs into ``frame``.
    """
    times = frame[TIME].tolist()
    if not times:
        return []
    cycles: list[tuple[int, int]] = []
    start = 0
    for i in range(1, len(times)):
        if (times[i] - times[i - 1]).total_seconds() > gap_seconds:
            cycles.append((start, i - 1))
            start = i
    cycles.append((start, len(times) - 1))
    return cycles


def cycle_bounds(frame: pd.DataFrame, cycle: tuple[int, int]) -> tuple:
    """The wall-clock start and end timestamps of a cycle."""
    start_row, end_row = cycle
    return frame[TIME].iloc[start_row], frame[TIME].iloc[end_row]


def chronological_split(
    frame: pd.DataFrame,
    truth: list[Segment],
    train_fraction: float = 0.7,
) -> tuple[pd.DataFrame, list[Segment], pd.DataFrame, list[Segment]]:
    """Split the raw stream in time, cutting only in an idle gap.

    Chronological rather than random because Test.csv is a separate, later
    recording -- a time-ordered split is the honest simulation of that. The cut
    lands between two cycles, never inside one, so no cycle's rows are shared
    across the two sides and there is no leakage.
    """
    cycles = find_cycles(frame)
    n_train_cycles = max(1, round(len(cycles) * train_fraction))
    split_row = cycles[n_train_cycles - 1][1]  # last row of the last fit cycle
    boundary = frame[TIME].iloc[split_row]

    fit_frame = frame.iloc[: split_row + 1].reset_index(drop=True)
    holdout_frame = frame.iloc[split_row + 1 :].reset_index(drop=True)
    fit_truth = [s for s in truth if s.end <= boundary]
    holdout_truth = [s for s in truth if s.start > boundary]

    return fit_frame, fit_truth, holdout_frame, holdout_truth
