"""Per-cycle feature extraction.

Physical reasoning: abnormal resistance (objects in the slide rail, rubber
strip jamming, leaf deformation) opposes the motor, so the motor must sustain
more current to keep the leaf moving. The inrush spike at the start and the
braking phase at the end are dominated by motor dynamics rather than by track
resistance, so the most informative window is the *mid-travel* portion.

That window is located by door-leaf travel fraction rather than by a fixed row
percentage, so cycles that run long or travel further than usual still have
their steady-state phase measured, not a misaligned slice of it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.data import CLOSE_CMD, CURRENT, EMF, OPEN_CMD, POSITION, VOLTAGE, cycle_bounds

# Fraction of total leaf travel treated as steady state.
MID_TRAVEL_START = 0.20
MID_TRAVEL_END = 0.85


def travel_fraction(position: np.ndarray) -> np.ndarray:
    """Map leaf position onto 0..1 progress through the cycle's own travel.

    Direction-aware and scaled to the cycle's observed range, so an Open that
    overshoots to 807 and a Close that ends at 1 are both handled.
    """
    lo, hi = float(position.min()), float(position.max())
    if hi - lo < 1e-9:
        return np.linspace(0.0, 1.0, len(position))
    scaled = (position - lo) / (hi - lo)
    # Closing runs high -> low, so invert it to make progress increase.
    if position[0] > position[-1]:
        scaled = 1.0 - scaled
    return scaled


def _stats(prefix: str, values: np.ndarray) -> dict[str, float]:
    return {
        f"{prefix}_mean": float(values.mean()),
        f"{prefix}_median": float(np.median(values)),
        f"{prefix}_std": float(values.std()),
        f"{prefix}_max": float(values.max()),
        f"{prefix}_p90": float(np.percentile(values, 90)),
        f"{prefix}_p75": float(np.percentile(values, 75)),
    }


def extract(frame: pd.DataFrame, cycle: tuple[int, int]) -> dict[str, float]:
    """Build the feature dictionary for one door cycle."""
    start_row, end_row = cycle
    rows = frame.iloc[start_row : end_row + 1]
    start_time, end_time = cycle_bounds(frame, cycle)

    current = rows[CURRENT].to_numpy(dtype=float)
    voltage = rows[VOLTAGE].to_numpy(dtype=float)
    emf = rows[EMF].to_numpy(dtype=float)
    position = rows[POSITION].to_numpy(dtype=float)

    # Operation comes from the command flags; on Train this recovers the
    # labelled Open/Close for all 110 cycles.
    is_open = float(rows[OPEN_CMD].mean()) > float(rows[CLOSE_CMD].mean())

    progress = travel_fraction(position)
    mid = (progress >= MID_TRAVEL_START) & (progress <= MID_TRAVEL_END)
    if mid.sum() < 5:  # degenerate cycle: fall back to the middle rows
        mid = np.zeros(len(current), dtype=bool)
        mid[len(current) // 5 : max(len(current) // 5 + 5, 4 * len(current) // 5)] = True

    features: dict[str, float] = {"is_open": float(is_open)}
    features.update(_stats("current", current))
    features.update(_stats("voltage", voltage))
    features.update(_stats("emf", emf))

    # The discriminative window.
    features["current_mid_mean"] = float(current[mid].mean())
    features["current_mid_median"] = float(np.median(current[mid]))
    features["current_mid_max"] = float(current[mid].max())
    features["current_mid_std"] = float(current[mid].std())
    features["voltage_mid_mean"] = float(voltage[mid].mean())
    features["emf_mid_mean"] = float(emf[mid].mean())

    # Ratios normalise away supply-level differences between doors, which the
    # info kit (Section 1.2) warns vary from door to door.
    features["current_per_emf"] = float(current.mean() / max(emf.mean(), 1e-6))
    features["current_mid_per_emf"] = float(
        current[mid].mean() / max(emf[mid].mean(), 1e-6)
    )
    features["voltage_per_emf"] = float(voltage.mean() / max(emf.mean(), 1e-6))
    features["power_proxy"] = float((current * voltage).mean())
    features["power_mid_proxy"] = float((current[mid] * voltage[mid]).mean())

    # Shape of the cycle.
    features["duration"] = (end_time - start_time).total_seconds()
    features["n_rows"] = float(len(rows))
    features["travel_range"] = float(position.max() - position.min())
    features["current_auc"] = float(current.sum() * 0.02)  # 20 ms sampling

    return features


def build_table(
    frame: pd.DataFrame, cycles: list[tuple[int, int]]
) -> pd.DataFrame:
    """Feature table for every cycle, one row each, with its time range."""
    records = []
    for cycle in cycles:
        record = extract(frame, cycle)
        start_time, end_time = cycle_bounds(frame, cycle)
        record["start_time"] = start_time
        record["end_time"] = end_time
        records.append(record)
    return pd.DataFrame(records)


FEATURE_COLUMNS = [
    "is_open",
    "current_mean", "current_median", "current_std", "current_max", "current_p90", "current_p75",
    "voltage_mean", "voltage_median", "voltage_std", "voltage_max", "voltage_p90", "voltage_p75",
    "emf_mean", "emf_median", "emf_std", "emf_max", "emf_p90", "emf_p75",
    "current_mid_mean", "current_mid_median", "current_mid_max", "current_mid_std",
    "voltage_mid_mean", "emf_mid_mean",
    "current_per_emf", "current_mid_per_emf", "voltage_per_emf",
    "power_proxy", "power_mid_proxy",
    "duration", "n_rows", "travel_range", "current_auc",
]
