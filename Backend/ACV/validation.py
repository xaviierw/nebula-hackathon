# Validation for ACV scoring
import pandas as pd
import numpy as np

COOLING_MODES = {"Automatic Cooling", "Full Cooling", "Half Cooling"}


def _gated_residual_matrix(df, demand_threshold=None, demand_quantile=0.5):
    """Returns (matrix, car_ids): matrix is (n_gated_rows x n_cars) of peer-relative
    residuals, one column per car, built only from rows that pass validity/cooling/demand
    gates for ALL cars simultaneously (so every row has a value for every car)."""
    car_ids = [f"0{i}" for i in range(1, 9)]
    shortfall_cols = {}
    for cid in car_ids:
        indoor, setpoint = f"car_{cid}_indoor_temp", f"car_{cid}_cooling_setpoint"
        mode_col, valid_col = f"car_{cid}_running_mode", f"car_{cid}_valid_status"
        if indoor not in df.columns or setpoint not in df.columns:
            continue
        s = df[indoor] - df[setpoint]
        if mode_col in df.columns:
            s = s.where(df[mode_col].isin(COOLING_MODES))
        if valid_col in df.columns:
            s = s.where(df[valid_col] == "Valid")
        shortfall_cols[cid] = s

    wide = pd.DataFrame(shortfall_cols)
    if demand_threshold is None:
        demand_threshold = df["train_ambient_ref"].quantile(demand_quantile)
    demand_mask = df["train_ambient_ref"] >= demand_threshold

    train_median = wide.median(axis=1)
    residual = wide.sub(train_median, axis=0)
    residual = residual[demand_mask].dropna(how="any")  # keep rows valid for every car
    return residual.to_numpy(), list(wide.columns)


def permutation_test(df, observed_car, n_permutations=2000, demand_quantile=0.5, seed=0):
    """p-value: fraction of permutations where the best RANDOM car's mean residual is >=
    the observed car's mean residual, under random within-timestamp reassignment."""
    rng = np.random.default_rng(seed)
    mat, car_ids = _gated_residual_matrix(df, demand_quantile=demand_quantile)
    if mat.size == 0 or observed_car not in car_ids:
        return None, None

    observed = mat[:, car_ids.index(observed_car)].mean()
    T, C = mat.shape
    best_null = np.empty(n_permutations)
    for i in range(n_permutations):
        idx = np.argsort(rng.random((T, C)), axis=1)
        shuffled = np.take_along_axis(mat, idx, axis=1)
        best_null[i] = shuffled.mean(axis=0).max()

    p_value = (best_null >= observed).mean()
    return observed, p_value


def cooling_delivered_ranking(df, demand_quantile=0.5):
    """Independent cross-check feature: ambient - indoor (peer-normalised), instead of
    indoor - setpoint. Agreement between the two is much stronger evidence than either alone."""
    car_ids = [f"0{i}" for i in range(1, 9)]
    delivered_cols = {}
    for cid in car_ids:
        indoor = f"car_{cid}_indoor_temp"
        mode_col, valid_col = f"car_{cid}_running_mode", f"car_{cid}_valid_status"
        if indoor not in df.columns:
            continue
        s = df["train_ambient_ref"] - df[indoor]
        if mode_col in df.columns:
            s = s.where(df[mode_col].isin(COOLING_MODES))
        if valid_col in df.columns:
            s = s.where(df[valid_col] == "Valid")
        delivered_cols[cid] = s

    wide = pd.DataFrame(delivered_cols)
    thresh = df["train_ambient_ref"].quantile(demand_quantile)
    demand_mask = df["train_ambient_ref"] >= thresh

    train_median = wide.median(axis=1)
    residual = train_median.to_frame().to_numpy() - wide.to_numpy()  # +ve = under-delivering
    residual = pd.DataFrame(residual, columns=wide.columns, index=wide.index)[demand_mask]

    scores = residual.mean().sort_values(ascending=False)
    return scores  # pandas Series, car_id -> score, ranked descending