"""Audit item 5: permutation test.

Shuffles the labels and reruns the CV pipeline unchanged. Under shuffled labels
a leak-free pipeline must collapse to chance (macro-F1 ~0.4-0.5 for a 3:1 split).
Anything meaningfully above that indicates structural leakage.

Read-only: imports the real training code, writes nothing.

    python audit/permutation_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from core.data import DATA_DIR, chronological_split, find_cycles, load_stream, load_truth
from core.features import FEATURE_COLUMNS, build_table
from training.train import RANDOM_STATE, build_candidates

N_PERMUTATIONS = 200


def main() -> None:
    stream = load_stream(DATA_DIR / "Train.csv")
    truth = load_truth(DATA_DIR / "Train_Segments_Answer.csv")
    fit_frame, fit_truth, _, _ = chronological_split(stream, truth)
    X = build_table(fit_frame, find_cycles(fit_frame))[FEATURE_COLUMNS]
    y = np.array([s.label for s in fit_truth])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    rng = np.random.default_rng(RANDOM_STATE)

    print(f"Permutation test: {N_PERMUTATIONS} label shuffles, {len(y)} cycles\n")
    print(f"{'model':22s} {'true F1':>9s} {'shuffled mean':>14s} "
          f"{'shuffled max':>13s} {'p-value':>9s}")
    print("-" * 72)

    for name, _ in build_candidates().items():
        true_f1 = f1_score(
            y, cross_val_predict(build_candidates()[name], X, y, cv=cv),
            average="macro",
        )
        scores = []
        for _ in range(N_PERMUTATIONS):
            y_shuffled = rng.permutation(y)
            predicted = cross_val_predict(
                build_candidates()[name], X, y_shuffled, cv=cv
            )
            scores.append(f1_score(y_shuffled, predicted, average="macro"))
        scores = np.array(scores)
        # Fraction of shuffles matching or beating the real score.
        p_value = (np.sum(scores >= true_f1) + 1) / (N_PERMUTATIONS + 1)
        print(f"{name:22s} {true_f1:9.4f} {scores.mean():14.4f} "
              f"{scores.max():13.4f} {p_value:9.4f}")

    print("\nA leak-free pipeline collapses to chance under shuffled labels.")
    print("p < 0.01 means the real score is not reachable by chance structure.")


if __name__ == "__main__":
    main()
