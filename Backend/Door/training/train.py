"""Train and select the Door cycle classifier.

Everything here is fitted on the *fit* portion of Train.csv only. The holdout
portion of Train.csv and Test.csv are never touched during fitting or model
selection -- the holdout is scored exactly once, at the end, by evaluate.py.

Four candidates are compared under identical stratified cross-validation:
  1. a physics-motivated per-operation current threshold (the baseline),
  2. logistic regression on the full feature set,
  3. gradient boosting on the full feature set,
  4. a random forest on the full feature set.
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
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from core.data import DATA_DIR, chronological_split, find_cycles, load_stream, load_truth
from core.features import FEATURE_COLUMNS, build_table
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


def build_candidates() -> dict[str, object]:
    return {
        "threshold_baseline": OperationThreshold(),
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
          f"{'abnormal F1':>12s} {'FN':>4s} {'FP':>4s}")
    print("-" * 72)

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
        results[name] = {
            "accuracy": accuracy, "macro_f1": macro_f1,
            "abnormal_f1": abnormal_f1,
            "false_negative": false_negative, "false_positive": false_positive,
        }
        print(f"{name:22s} {accuracy:12.4f} {macro_f1:12.4f} {abnormal_f1:12.4f} "
              f"{false_negative:4d} {false_positive:4d}")

    # Select on macro-F1, tie-broken toward the simpler, explainable model.
    best_f1 = max(r["macro_f1"] for r in results.values())
    tied = [n for n, r in results.items() if best_f1 - r["macro_f1"] < 1e-9]
    chosen = "threshold_baseline" if "threshold_baseline" in tied else tied[0]
    print(f"\nBest CV macro-F1: {best_f1:.4f}, achieved by: {', '.join(tied)}")
    print(f"Selected: {chosen}"
          + (" (tie broken toward the explainable baseline)" if len(tied) > 1 else ""))

    model = build_candidates()[chosen]
    model.fit(X, y)

    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump({"model": model, "features": FEATURE_COLUMNS, "name": chosen},
                MODEL_DIR / "door_model.joblib")

    report = {"selected": chosen, "cv_results": results,
              "fit_cycles": len(y), "fit_abnormal": n_abnormal}
    if isinstance(model, OperationThreshold):
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
            "feature": model.feature,
            "threshold_open": model.thresholds_[1.0],
            "threshold_close": model.thresholds_[0.0],
            "margin_open": model.margins_[1.0],
            "margin_close": model.margins_[0.0],
            "labels": {"above": ABNORMAL, "below": NORMAL},
            "fitted_on": "Train.csv chronological fit split (first 70% of cycles)",
            "fit_cycles": len(y),
            "cv_macro_f1": results[chosen]["macro_f1"],
        }
        (MODEL_DIR / "door_model.json").write_text(
            json.dumps(portable, indent=2), newline="\n"
        )
        print(f"Portable model  -> {MODEL_DIR / 'door_model.json'} (no sklearn needed)")

    (MODEL_DIR / "training_report.json").write_text(
        json.dumps(report, indent=2), newline="\n"
    )
    print(f"Pickled model   -> {MODEL_DIR / 'door_model.joblib'}")
    print(f"Training report -> {MODEL_DIR / 'training_report.json'}")


if __name__ == "__main__":
    main()
