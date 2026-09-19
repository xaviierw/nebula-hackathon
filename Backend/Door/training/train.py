"""Train and select the Door cycle classifier.

Everything here is fitted on the *fit* portion of Train.csv only. The holdout
portion of Train.csv and Test.csv are never touched during fitting or model
selection -- the holdout is scored exactly once, at the end, by evaluate.py.

Every fitted quantity is fitted inside its fold: the thresholds via each
estimator's own .fit(), which cross_val_predict calls on training indices only,
and the scaler via the Pipeline that wraps it. The one thing NOT chosen inside
the loop is the feature and its mid-travel window -- see the caveat in
core/features.py.

Five candidates are compared under identical cross-validation:
  1. a per-operation cut at median + k*MAD of the Normal cycles (robust),
  2. the older per-operation midpoint threshold, kept for comparison,
  3. logistic regression on the full feature set,
  4. gradient boosting on the full feature set,
  5. a random forest on the full feature set.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from core.data import (
    CURRENT, DATA_DIR, POSITION, TIME, chronological_split, find_cycles,
    load_stream, load_truth,
)
from core.features import FEATURE_COLUMNS, build_table, travel_fraction
from core.scoring import ABNORMAL, NORMAL

MODEL_DIR = Path(__file__).resolve().parents[1] / "model"
RANDOM_STATE = 42


class OperationThreshold(BaseEstimator, ClassifierMixin):
    """Per-operation threshold on steady-state motor current.

    Fits one cut point for Open cycles and one for Close cycles, each placed at
    the midpoint between the highest Normal and the lowest Abnormal value seen
    in training. Open and Close have entirely different current profiles, so a
    single global threshold cannot work -- which is the failure mode the info
    kit describes in Section 1.2.
    """

    def __init__(self, feature: str = "current_mid_mean"):
        self.feature = feature

    def fit(self, X: pd.DataFrame, y):
        y = np.asarray(y)
        self.classes_ = np.array([ABNORMAL, NORMAL])
        self.thresholds_ = {}
        self.margins_ = {}
        for is_open in (0.0, 1.0):
            mask = X["is_open"].to_numpy() == is_open
            if mask.sum() == 0:
                self.thresholds_[is_open] = np.inf
                self.margins_[is_open] = 0.0
                continue
            values = X.loc[mask, self.feature].to_numpy()
            labels = y[mask]
            normal = values[labels == NORMAL]
            abnormal = values[labels == ABNORMAL]
            if len(normal) == 0 or len(abnormal) == 0:
                # Degenerate fold: fall back to the midrange of what we have.
                self.thresholds_[is_open] = float(values.mean())
                self.margins_[is_open] = 0.0
                continue
            high_normal, low_abnormal = normal.max(), abnormal.min()
            self.thresholds_[is_open] = float((high_normal + low_abnormal) / 2)
            self.margins_[is_open] = float(low_abnormal - high_normal)
        return self

    def predict(self, X: pd.DataFrame):
        values = X[self.feature].to_numpy()
        cuts = np.array([self.thresholds_[v] for v in X["is_open"].to_numpy()])
        return np.where(values > cuts, ABNORMAL, NORMAL)


# Robust-threshold multipliers, one per operation, chosen in
# audit/threshold_k_sweep.py by placing each cut midway between the highest
# Normal and the lowest Abnormal seen in training -- the point that maximises
# tolerance to drift in either direction. They differ because the two normal
# clusters have very different spreads (Open MAD 2.40 mA, Close MAD 0.74 mA).
K_OPEN = 16.0
K_CLOSE = 83.0


class MADThreshold(BaseEstimator, ClassifierMixin):
    """Per-operation cut at median + k*MAD of the *Normal* cycles.

    Replaces OperationThreshold's midpoint rule, which read the lowest Abnormal
    value and so was set by exactly two extreme points: withholding one mild
    fault swung the Close cut by 60 mA and caused a missed fault (audit item 6).

    This estimator never looks at an Abnormal value. The cut is anchored to the
    Normal cluster's robust centre and spread, both computed from all Normal
    cycles in the fold, so removing a fault from training cannot move it. MAD is
    the raw median absolute deviation (multiply by 1.4826 for sigma units).
    """

    def __init__(self, feature: str = "current_mid_mean",
                 k_open: float = K_OPEN, k_close: float = K_CLOSE):
        self.feature = feature
        self.k_open = k_open
        self.k_close = k_close

    @staticmethod
    def _mad(values: np.ndarray) -> float:
        return float(np.median(np.abs(values - np.median(values))))

    def fit(self, X: pd.DataFrame, y):
        y = np.asarray(y)
        self.classes_ = np.array([ABNORMAL, NORMAL])
        self.thresholds_ = {}
        self.margins_ = {}
        for is_open, k in ((0.0, self.k_close), (1.0, self.k_open)):
            mask = X["is_open"].to_numpy() == is_open
            values = X.loc[mask, self.feature].to_numpy()
            labels = y[mask]
            normal = values[labels == NORMAL]
            if len(normal) == 0:
                # Degenerate fold: no Normal cycles to anchor on.
                self.thresholds_[is_open] = float(values.mean()) if len(values) else np.inf
                self.margins_[is_open] = 0.0
                continue
            self.thresholds_[is_open] = float(np.median(normal) + k * self._mad(normal))
            # Headroom between the cut and the highest Normal, for the app's
            # confidence proxy -- reported, never used to place the cut.
            self.margins_[is_open] = float(self.thresholds_[is_open] - normal.max())
        return self

    def predict(self, X: pd.DataFrame):
        values = X[self.feature].to_numpy()
        cuts = np.array([self.thresholds_[v] for v in X["is_open"].to_numpy()])
        return np.where(values > cuts, ABNORMAL, NORMAL)


N_BLOCKS = 5


def blocked_cv_macro_f1(model_name: str, X: pd.DataFrame, y: np.ndarray) -> tuple[float, float]:
    """Leave-one-contiguous-time-block-out macro-F1 and abnormal recall.

    The stratified CV above shuffles, so cycles recorded seconds apart can sit
    on opposite sides of a fold boundary -- which makes it optimistic. Holding
    out whole time blocks is the stricter estimate. Grouping by door would be
    stricter still, but no door identifier exists in the data (see the audit
    note in README terms: Train.csv and Test.csv carry 17 columns, none of them
    Car Type, Car Number or Door Number).

    Reported alongside the stratified figure rather than replacing it: with 19
    abnormal cycles across 5 blocks, some blocks hold only one, so the per-block
    F1 is noisy.
    """
    groups = np.minimum((np.arange(len(y)) * N_BLOCKS) // len(y), N_BLOCKS - 1)
    predicted = np.empty(len(y), dtype=object)
    for block in range(N_BLOCKS):
        test = groups == block
        if len(set(y[~test])) < 2:
            predicted[test] = NORMAL
            continue
        model = build_candidates()[model_name]
        model.fit(X[~test], y[~test])
        predicted[test] = model.predict(X[test])
    return (f1_score(y, predicted, average="macro"),
            recall_score(y, predicted, pos_label=ABNORMAL))


def build_candidates() -> dict[str, object]:
    return {
        "threshold_mad": MADThreshold(),
        "threshold_midpoint": OperationThreshold(),
        "logistic_regression": Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(
                max_iter=5000, class_weight="balanced", random_state=RANDOM_STATE
            )),
        ]),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=200, max_depth=2, learning_rate=0.05,
            random_state=RANDOM_STATE,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=400, max_depth=4, class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
    }


ENVELOPE_GRID = 200


def export_reference(frame, cycles, table, labels, path: Path) -> dict:
    """Save what the runtime needs to know about Train.csv, so it needs nothing else.

    Two things, both computed here and never at prediction time:

    - `durations`: the observed duration envelope per operation. The guard in
      prediction/predict.py flags any segment outside it, which is what catches
      a truncated file emitting a partial cycle.
    - `envelopes`: motor current resampled onto a fixed travel-fraction grid, as
      min/max/mean per (operation, status). A UI can draw one cycle against its
      class bands without shipping Train.csv.

    Computed over ALL of Train.csv, not the fit split: these describe the data,
    not the model, so withholding the holdout would only make them narrower for
    no benefit.
    """
    grid = np.linspace(0.0, 1.0, ENVELOPE_GRID)
    is_open = table["is_open"].to_numpy() > 0.5
    secs = (table["end_time"] - table["start_time"]).dt.total_seconds().to_numpy()
    durations, envelopes = {}, {}

    for op, want_open in (("Open", True), ("Close", False)):
        sel = np.flatnonzero(is_open == want_open)
        if len(sel) == 0:
            continue
        durations[op] = {
            "min": float(secs[sel].min()),
            "max": float(secs[sel].max()),
            "n": int(len(sel)),
        }
        for status, key in ((NORMAL, "Normal"), (ABNORMAL, "Abnormal")):
            rows = [i for i in sel if labels[i] == status]
            if not rows:
                continue
            curves = []
            for i in rows:
                start_row, end_row = cycles[i]
                window = frame.iloc[start_row : end_row + 1]
                position = window[POSITION].to_numpy(dtype=float)
                current = window[CURRENT].to_numpy(dtype=float)
                progress = travel_fraction(position)
                order = np.argsort(progress)
                curves.append(np.interp(grid, progress[order], current[order]))
            curves = np.asarray(curves)
            envelopes[f"{op}/{key}"] = {
                "n": len(rows),
                "min": curves.min(0).round(2).tolist(),
                "max": curves.max(0).round(2).tolist(),
                "mean": curves.mean(0).round(2).tolist(),
            }

    interval = pd.Series(frame[TIME]).diff().dt.total_seconds().mode().iloc[0]
    reference = {
        "_comment": "Derived from Train.csv at training time so inference needs "
                    "only this file. Current in mA against travel fraction.",
        "grid_points": ENVELOPE_GRID,
        "grid": grid.round(6).tolist(),
        "sampling_interval_seconds": float(interval),
        "durations": durations,
        "envelopes": envelopes,
    }
    path.write_text(json.dumps(reference, indent=1), newline=chr(10))
    return reference


def main() -> None:
    train_stream = load_stream(DATA_DIR / "Train.csv")
    truth = load_truth(DATA_DIR / "Train_Segments_Answer.csv")

    fit_frame, fit_truth, _, _ = chronological_split(train_stream, truth)
    fit_cycles = find_cycles(fit_frame)
    table = build_table(fit_frame, fit_cycles)
    X = table[FEATURE_COLUMNS]
    y = np.array([s.label for s in fit_truth])

    n_abnormal = int((y == ABNORMAL).sum())
    print(f"Fit set: {len(y)} cycles "
          f"({len(y) - n_abnormal} Normal / {n_abnormal} Abnormal)")
    print(f"Features: {len(FEATURE_COLUMNS)}")
    print("Holdout and Test are untouched here.\n")

    # 5-fold stratified CV keeps the 3:1 class ratio in every fold.
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    print(f"{'model':22s} {'CV accuracy':>12s} {'CV macro-F1':>12s} "
          f"{'abnormal F1':>12s} {'FN':>4s} {'FP':>4s} "
          f"{'blocked-F1':>11s} {'blocked-rec':>12s}")
    print("-" * 97)

    results = {}
    for name, model in build_candidates().items():
        predicted = cross_val_predict(model, X, y, cv=cv)
        accuracy = accuracy_score(y, predicted)
        macro_f1 = f1_score(y, predicted, average="macro")
        abnormal_f1 = f1_score(y, predicted, pos_label=ABNORMAL)
        # Rows = truth, columns = prediction, with labels [ABNORMAL, NORMAL].
        matrix = confusion_matrix(y, predicted, labels=[ABNORMAL, NORMAL])
        false_negative = int(matrix[0, 1])  # abnormal called normal -- the costly one
        false_positive = int(matrix[1, 0])
        blocked_f1, blocked_recall = blocked_cv_macro_f1(name, X, y)
        results[name] = {
            "accuracy": accuracy, "macro_f1": macro_f1,
            "abnormal_f1": abnormal_f1,
            "false_negative": false_negative, "false_positive": false_positive,
            "blocked_macro_f1": blocked_f1, "blocked_abnormal_recall": blocked_recall,
        }
        print(f"{name:22s} {accuracy:12.4f} {macro_f1:12.4f} {abnormal_f1:12.4f} "
              f"{false_negative:4d} {false_positive:4d} "
              f"{blocked_f1:11.4f} {blocked_recall:12.4f}")

    # Select on macro-F1, tie-broken toward the simpler, explainable model.
    best_f1 = max(r["macro_f1"] for r in results.values())
    tied = [n for n, r in results.items() if best_f1 - r["macro_f1"] < 1e-9]
    # Tie-break toward the robust, explainable estimator, then the old midpoint.
    preference = ["threshold_mad", "threshold_midpoint"]
    chosen = next((n for n in preference if n in tied), tied[0])
    print(f"\nBest CV macro-F1: {best_f1:.4f}, achieved by: {', '.join(tied)}")
    print(f"Selected: {chosen}"
          + (" (tie broken toward the robust, explainable estimator)"
             if len(tied) > 1 else ""))

    # Fix 4: both headline numbers, always reported together.
    print()
    print(f"  stratified 5-fold macro-F1 : {results[chosen]['macro_f1']:.4f}"
          "   (shuffled -- optimistic, adjacent cycles can cross folds)")
    print(f"  blocked   5-fold macro-F1 : {results[chosen]['blocked_macro_f1']:.4f}"
          "   (whole time blocks held out -- the honest figure)")
    print(f"  blocked abnormal recall   : "
          f"{results[chosen]['blocked_abnormal_recall']:.4f}")
    print("  Report both: a bare 1.0000 reads as a leaky split, while the")
    print("  pair shows the gap was measured rather than assumed.")

    model = build_candidates()[chosen]
    model.fit(X, y)

    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump({"model": model, "features": FEATURE_COLUMNS, "name": chosen},
                MODEL_DIR / "door_model.joblib")

    report = {"selected": chosen, "cv_results": results,
              "fit_cycles": len(y), "fit_abnormal": n_abnormal}
    if isinstance(model, (MADThreshold, OperationThreshold)):
        report["thresholds"] = {
            "close": model.thresholds_[0.0], "open": model.thresholds_[1.0],
        }
        report["separation_margins"] = {
            "close": model.margins_[0.0], "open": model.margins_[1.0],
        }
        print(f"\nFitted thresholds on '{model.feature}':")
        for op, key in (("Close", 0.0), ("Open", 1.0)):
            print(f"  {op:5s}: cut at {model.thresholds_[key]:7.1f} mA "
                  f"(gap between classes: {model.margins_[key]:.1f} mA)")

        # Portable, sklearn-free export. The shipped app and predict.py load
        # this rather than the pickle, so inference needs only numpy/pandas --
        # which matters because Smart App Control blocks sklearn's binaries on
        # the Windows machine the app has to run on.
        portable = {
            "model_type": "operation_threshold",
        "estimator": chosen,
            "feature": model.feature,
            "threshold_open": model.thresholds_[1.0],
            "threshold_close": model.thresholds_[0.0],
            "margin_open": model.margins_[1.0],
            "margin_close": model.margins_[0.0],
            "labels": {"above": ABNORMAL, "below": NORMAL},
            "fitted_on": "Train.csv chronological fit split (first 70% of cycles)",
            "fit_cycles": len(y),
            "cv_macro_f1_stratified": results[chosen]["macro_f1"],
            "cv_macro_f1_blocked": results[chosen]["blocked_macro_f1"],
            "cv_abnormal_recall_blocked": results[chosen]["blocked_abnormal_recall"],
            # Kept under the old key so anything reading it still works.
            "cv_macro_f1": results[chosen]["macro_f1"],
        }
        (MODEL_DIR / "door_model.json").write_text(
            json.dumps(portable, indent=2), newline="\n"
        )
        print(f"Portable model  -> {MODEL_DIR / 'door_model.json'} (no sklearn needed)")

    # Reference data for the runtime guards and the app's plots. Uses the whole
    # of Train.csv -- see export_reference's docstring for why that is safe.
    all_cycles = find_cycles(train_stream)
    all_table = build_table(train_stream, all_cycles)
    reference = export_reference(
        train_stream, all_cycles, all_table, [s.label for s in truth],
        MODEL_DIR / "door_reference.json",
    )
    print()
    print("Duration envelope derived from all Train cycles:")
    for op, d in reference["durations"].items():
        print(f"  {op:5s}: {d['min']:.3f}s .. {d['max']:.3f}s  (n={d['n']})")
    print(f"  sampling interval: {reference['sampling_interval_seconds']:.3f}s")
    print(f"  envelopes: {', '.join(reference['envelopes'])}")
    print(f"Reference data  -> {MODEL_DIR / 'door_reference.json'}")

    (MODEL_DIR / "training_report.json").write_text(
        json.dumps(report, indent=2), newline="\n"
    )
    print(f"Pickled model   -> {MODEL_DIR / 'door_model.joblib'}")
    print(f"Training report -> {MODEL_DIR / 'training_report.json'}")


if __name__ == "__main__":
    main()
