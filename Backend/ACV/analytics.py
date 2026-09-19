# Contains core scoring & ranking algorithms
import pandas as pd
import numpy as np

COOLING_MODES = {"Automatic Cooling", "Full Cooling", "Half Cooling"}


def calculate_shortfall_and_rank(df, ambient_quantile=0.5, return_scores=False):
    """Calculates the peer-relative cooling shortfall and ranks cars.

    ambient_quantile: fraction (0-1) used as a PER-FILE adaptive threshold instead of a
    fixed absolute temperature — a fixed value (e.g. 26.0) can silently gate out almost
    everything on a cooler file, or almost nothing on a hotter one.
    """
    shortfall_cols = []
    rel_cols = []

    # 1. Absolute shortfall (Indoor - Setpoint), gated to valid + cooling-mode rows only
    for i in range(1, 9):
        car_id = f"0{i}"
        indoor = f"car_{car_id}_indoor_temp"
        setpoint = f"car_{car_id}_cooling_setpoint"
        mode_col = f"car_{car_id}_running_mode"
        valid_col = f"car_{car_id}_valid_status"
        abs_shortfall = f"car_{car_id}_abs_shortfall"

        if indoor in df.columns and setpoint in df.columns:
            s = df[indoor] - df[setpoint]
            # gate out Stop/Ventilation/Emergency rows and info-invalid rows
            if mode_col in df.columns:
                s = s.where(df[mode_col].isin(COOLING_MODES))
            if valid_col in df.columns:
                s = s.where(df[valid_col] == "Valid")
            df[abs_shortfall] = s
            shortfall_cols.append(abs_shortfall)

    # 2. Train-level median shortfall at each timestamp
    df['train_median_shortfall'] = df[shortfall_cols].median(axis=1)

    # 3. Peer-relative shortfall
    for i in range(1, 9):
        car_id = f"0{i}"
        abs_shortfall = f"car_{car_id}_abs_shortfall"
        rel_shortfall = f"car_{car_id}_rel_shortfall"

        if abs_shortfall in df.columns:
            df[rel_shortfall] = df[abs_shortfall] - df['train_median_shortfall']
            rel_cols.append(rel_shortfall)

    # 4. Filter for high-demand windows — PER-FILE adaptive threshold (was a fixed 26.0)
    ambient_threshold = df['train_ambient_ref'].quantile(ambient_quantile)
    high_demand_df = df[df['train_ambient_ref'] >= ambient_threshold]
    if high_demand_df.empty:
        high_demand_df = df

    # 5. Aggregate. .mean() not .sum() — .sum() rewards cars that simply have MORE valid
    # gated rows, independent of whether they're actually cooling worse.
    scores = high_demand_df[rel_cols].mean()
    scores.index = [col.split('_')[1] for col in scores.index]

    if return_scores:
        return scores  # car_id -> raw shortfall score, NOT yet ranked/joined
    ranked = scores.sort_values(ascending=False)
    return "|".join(ranked.index)


def calculate_delivered_and_rank(df, ambient_quantile=0.5, return_scores=False):
    """Second, independently-derived feature: ambient - indoor (peer-normalised), instead
    of indoor - setpoint. Uses a different pair of columns, so agreement between this and
    calculate_shortfall_and_rank is real corroborating evidence, not the same signal twice."""
    delivered_cols = {}
    for i in range(1, 9):
        car_id = f"0{i}"
        indoor = f"car_{car_id}_indoor_temp"
        mode_col = f"car_{car_id}_running_mode"
        valid_col = f"car_{car_id}_valid_status"
        if indoor not in df.columns:
            continue
        s = df['train_ambient_ref'] - df[indoor]
        if mode_col in df.columns:
            s = s.where(df[mode_col].isin(COOLING_MODES))
        if valid_col in df.columns:
            s = s.where(df[valid_col] == "Valid")
        delivered_cols[car_id] = s

    wide = pd.DataFrame(delivered_cols)
    ambient_threshold = df['train_ambient_ref'].quantile(ambient_quantile)
    high_demand_mask = df['train_ambient_ref'] >= ambient_threshold
    wide_gated = wide[high_demand_mask] if high_demand_mask.any() else wide

    train_median = wide_gated.median(axis=1)
    residual = train_median.to_frame().to_numpy() - wide_gated.to_numpy()  # +ve = under-delivering
    residual = pd.DataFrame(residual, columns=wide_gated.columns, index=wide_gated.index)

    scores = residual.mean()
    if return_scores:
        return scores
    ranked = scores.sort_values(ascending=False)
    return "|".join(ranked.index)


def combined_borda_rank(df, ambient_quantile=0.5):
    """Combines shortfall + cooling-delivered rankings via Borda count (rank position,
    not raw score) — more robust than averaging raw scores, which have different scales.
    Also returns a simple agreement flag: did the two features pick the same top car?"""
    shortfall_scores = calculate_shortfall_and_rank(df, ambient_quantile, return_scores=True)
    delivered_scores = calculate_delivered_and_rank(df, ambient_quantile, return_scores=True)

    car_ids = sorted(set(shortfall_scores.index) | set(delivered_scores.index))
    n = len(car_ids)

    def to_borda_points(scores):
        # rank descending (1st place gets n points, last gets 1)
        ranked = scores.reindex(car_ids).sort_values(ascending=False)
        points = {car: n - i for i, car in enumerate(ranked.index)}
        return points

    p1 = to_borda_points(shortfall_scores)
    p2 = to_borda_points(delivered_scores)
    total = {car: p1.get(car, 0) + p2.get(car, 0) for car in car_ids}

    ranked_cars = sorted(total, key=lambda c: total[c], reverse=True)
    agreement = shortfall_scores.idxmax() == delivered_scores.idxmax()
    return "|".join(ranked_cars), agreement