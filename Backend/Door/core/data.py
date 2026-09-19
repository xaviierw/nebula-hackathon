"""Loading the continuous door stream, cutting it into cycles, and splitting it.

The stream is sampled at a rigid 20 ms *within* a door cycle, with long
irregular idle gaps (tens of seconds) between cycles. Cycle boundaries are
therefore breaks in sampling continuity, not transitions of the opening/closing
flags -- which is what the info kit's Section 2.2 note is pointing at.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
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

# Fallback gap threshold, used only when a stream is too uniform for one to be
# derived (see derive_gap_seconds). Intra-cycle sampling is 20 ms and
# inter-cycle gaps are 10-59 s, so any threshold in that enormous range yields
# identical segmentation -- this is a structural constant, not a tuned
# hyperparameter. The derived threshold is preferred because it reads the
# separation out of the file in hand rather than assuming this one holds.
GAP_SECONDS = 0.1

# A derived threshold is only trusted when the two populations are separated by
# at least this ratio. Below it, the largest jump is more likely a dropped
# sample than a cycle boundary, so the constant above is used instead.
MIN_SEPARATION_RATIO = 10.0

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


def derive_gap_seconds(frame: pd.DataFrame) -> float:
    """Derive the cycle-boundary threshold from the stream's own timing.

    Sampling intervals in these streams fall into two populations with nothing
    between them: 20 ms within a cycle, tens of seconds between cycles. So the
    threshold is read off the data -- find the largest *ratio* jump in the
    sorted distinct intervals and sit at its geometric midpoint.

    Ratio rather than absolute difference, because the two populations differ by
    orders of magnitude; and geometric rather than arithmetic midpoint, so the
    threshold sits centrally on a log scale rather than hugging the smaller
    population.

    Falls back to GAP_SECONDS when the stream is too uniform to split (a single
    cycle, or fewer than two distinct intervals) or when the largest jump is
    smaller than MIN_SEPARATION_RATIO, which would make it a dropped sample
    rather than a cycle boundary.

    On both supplied streams this reproduces the hardcoded constant's
    segmentation exactly: Train 0.4520 s, Test 0.4714 s, 110 and 38 cycles.
    """
    deltas = frame[TIME].diff().dt.total_seconds().dropna().unique()
    deltas = np.sort(deltas[deltas > 0])
    if len(deltas) < 2:
        return GAP_SECONDS
    ratios = deltas[1:] / deltas[:-1]
    i = int(ratios.argmax())
    if ratios[i] < MIN_SEPARATION_RATIO:
        return GAP_SECONDS
    return float(np.sqrt(deltas[i] * deltas[i + 1]))


def find_cycles(
    frame: pd.DataFrame, gap_seconds: float | None = None
) -> list[tuple[int, int]]:
    """Split the stream into cycles at breaks in sampling continuity.

    ``gap_seconds`` defaults to a threshold derived from this stream
    (derive_gap_seconds); pass a number to override it.

    Returns inclusive ``(start_row, end_row)`` index pairs into ``frame``.
    """
    if gap_seconds is None:
        gap_seconds = derive_gap_seconds(frame)
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
