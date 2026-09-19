"""Feature extraction for ACV telemetry."""

from __future__ import annotations

import re

import pandas as pd
import numpy as np

from .errors import AcvInputError

COOLING_MODES = {"Automatic Cooling", "Full Cooling", "Half Cooling"}


def calculate_train_ambient_ref(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates train-level ambient reference across populated end/car sensors."""
    ambient_cols = [col for col in df.columns if '_ambient_temp' in col]
    if ambient_cols:
        df['train_ambient_ref'] = df[ambient_cols].median(axis=1)
    else:
        df['train_ambient_ref'] = np.nan
    return df


def _car_ids(df: pd.DataFrame) -> list[str]:
    """Return identifiers discovered from normalized source headers."""
    ids: list[str] = []
    for column in df.columns:
        match = re.match(r"^car_(.+?)_(?:ambient_temp|indoor_temp|cooling_setpoint|running_mode|valid_status)$", str(column))
        if match and match.group(1) not in ids:
            ids.append(match.group(1))
    return ids


def extract_features(df: pd.DataFrame, ambient_quantile: float = 0.5) -> dict:
    """Extracts peer-relative shortfall and delivered cooling score vectors."""
    car_ids = _car_ids(df)

    # 1. Absolute shortfall (Indoor - Setpoint)
    shortfall_cols = []
    shortfall_ids = []
    for car_id in car_ids:
        indoor = f"car_{car_id}_indoor_temp"
        setpoint = f"car_{car_id}_cooling_setpoint"
        mode_col = f"car_{car_id}_running_mode"
        valid_col = f"car_{car_id}_valid_status"
        abs_shortfall = f"car_{car_id}_abs_shortfall"

        if indoor in df.columns and setpoint in df.columns:
            s = df[indoor] - df[setpoint]
            if mode_col in df.columns:
                s = s.where(df[mode_col].isin(COOLING_MODES))
            if valid_col in df.columns:
                s = s.where(df[valid_col] == "Valid")
            df[abs_shortfall] = s
            shortfall_cols.append(abs_shortfall)
            shortfall_ids.append(car_id)

    if not shortfall_cols:
        raise AcvInputError(
            "The ACV export does not contain complete indoor and cooling-setpoint readings."
        )

    df['train_median_shortfall'] = df[shortfall_cols].median(axis=1)

    rel_cols = []
    for car_id in shortfall_ids:
        abs_shortfall = f"car_{car_id}_abs_shortfall"
        rel_shortfall = f"car_{car_id}_rel_shortfall"
        if abs_shortfall in df.columns:
            df[rel_shortfall] = df[abs_shortfall] - df['train_median_shortfall']
            rel_cols.append(rel_shortfall)

    # Filter by adaptive ambient threshold
    ambient_threshold = df['train_ambient_ref'].quantile(ambient_quantile)
    high_demand_mask = df['train_ambient_ref'] >= ambient_threshold
    high_demand_df = df[high_demand_mask] if high_demand_mask.any() else df

    shortfall_scores = high_demand_df[rel_cols].mean()
    shortfall_scores.index = shortfall_ids

    # Delivered cooling scores: ambient - indoor
    delivered_cols = {}
    for car_id in car_ids:
        indoor = f"car_{car_id}_indoor_temp"
        mode_col = f"car_{car_id}_running_mode"
        valid_col = f"car_{car_id}_valid_status"
        if indoor in df.columns:
            s = df['train_ambient_ref'] - df[indoor]
            if mode_col in df.columns:
                s = s.where(df[mode_col].isin(COOLING_MODES))
            if valid_col in df.columns:
                s = s.where(df[valid_col] == "Valid")
            delivered_cols[car_id] = s

    wide_deliv = pd.DataFrame(delivered_cols)
    wide_deliv_gated = wide_deliv[high_demand_mask] if high_demand_mask.any() else wide_deliv
    train_median_deliv = wide_deliv_gated.median(axis=1)
    delivered_scores = wide_deliv_gated.rsub(train_median_deliv, axis=0).mean()

    score_table = pd.concat(
        [shortfall_scores.rename("shortfall"), delivered_scores.rename("delivered")],
        axis=1,
    )
    unusable = score_table.index[~np.isfinite(score_table).all(axis=1)].tolist()
    if unusable:
        raise AcvInputError(
            "There are no usable cooling observations for: "
            + ", ".join(f"car {car_id}" for car_id in unusable)
            + ". Check running mode, validity flags and temperature readings."
        )

    return {
        "shortfall_scores": score_table["shortfall"],
        "delivered_scores": score_table["delivered"],
    }
