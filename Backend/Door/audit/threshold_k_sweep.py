"""Audit: choose k for the median + k*MAD threshold, per operation.

Replaces the min/max-midpoint cut, which is determined by exactly two extreme
points and swung 60 mA when one mild fault was withheld (audit item 6).

median + k*MAD is anchored to the NORMAL cluster only -- it never reads an
abnormal value -- so withholding a mild fault cannot move it. MAD here is the
raw median absolute deviation, unscaled (multiply by 1.4826 for sigma units).

The sweep prints, for each k and each operation: the cut, the margins that
matter on both sides, any misclassifications it causes, and the blocked-CV
macro-F1 it yields.

    python audit/threshold_k_sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from sklearn.metrics import f1_score

from core.data import DATA_DIR, chronological_split, find_cycles, load_stream, load_truth
from core.features import build_table
from core.scoring import ABNORMAL, NORMAL

FEATURE = "current_mid_mean"
K_VALUES = [3, 5, 8, 10, 12, 15, 20, 25, 30, 40, 60, 100]
N_BLOCKS = 5


def mad(values: np.ndarray) -> float:
    """Raw median absolute deviation."""
    return float(np.median(np.abs(values - np.median(values))))


def cut_from(normal_values: np.ndarray, k: float) -> float:
    return float(np.median(normal_values) + k * mad(normal_values))


def blocked_f1(values, labels, groups, k) -> float:
    """Leave-one-time-block-out macro-F1 for this k, cut refit per fold."""
    predicted = np.empty(len(labels), dtype=object)
    for block in sorted(set(groups)):
        test = groups == block
        train_normal = values[(~test) & (labels == NORMAL)]
        if len(train_normal) == 0:
            predicted[test] = NORMAL
            continue
        cut = cut_from(train_normal, k)
        predicted[test] = np.where(values[test] > cut, ABNORMAL, NORMAL)
    return f1_score(labels, predicted, average="macro")


def main() -> None:
    stream = load_stream(DATA_DIR / "Train.csv")
    truth = load_truth(DATA_DIR / "Train_Segments_Answer.csv")
    fit_frame, fit_truth, _, _ = chronological_split(stream, truth)
    table = build_table(fit_frame, find_cycles(fit_frame))
    labels = np.array([s.label for s in fit_truth])
    groups = np.minimum((np.arange(len(labels)) * N_BLOCKS) // len(labels), N_BLOCKS - 1)

    for operation, is_open in (("Open", True), ("Close", False)):
        mask = (table["is_open"] > 0.5).to_numpy() == is_open
        values = table.loc[mask, FEATURE].to_numpy()
        lab = labels[mask]
        grp = groups[mask]
        normal = values[lab == NORMAL]
        abnormal = values[lab == ABNORMAL]

        print(f"\n{'='*94}")
        print(f"{operation}:  {len(normal)} Normal, {len(abnormal)} Abnormal   "
              f"(fit split of Train.csv)")
        print(f"  Normal   median={np.median(normal):7.1f}  MAD={mad(normal):5.2f}  "
              f"range {normal.min():.1f}..{normal.max():.1f}")
        print(f"  Abnormal                              "
              f"range {abnormal.min():.1f}..{abnormal.max():.1f}")
        print(f"  usable band for the cut: ({normal.max():.1f}, {abnormal.min():.1f})"
              f"  width {abnormal.min()-normal.max():.1f} mA")
        print(f"{'='*94}")
        print(f"{'k':>4s} {'cut':>8s} {'gap below':>10s} {'gap above':>10s} "
              f"{'FP':>3s} {'FN':>3s} {'worst FP over':>14s} {'worst FN under':>15s} "
              f"{'blockedF1':>10s}")
        print("-" * 94)

        for k in K_VALUES:
            cut = cut_from(normal, k)
            # Headroom on each side: distance from the cut to the nearest
            # correctly-placed point of each class.
            below = normal[normal <= cut]
            above = abnormal[abnormal > cut]
            gap_below = cut - below.max() if len(below) else float("nan")
            gap_above = above.min() - cut if len(above) else float("nan")
            # Errors: a Normal above the cut is a false positive, an Abnormal
            # below it a missed fault.
            fp = normal[normal > cut]
            fn = abnormal[abnormal <= cut]
            worst_fp = (fp.max() - cut) if len(fp) else 0.0
            worst_fn = (cut - fn.min()) if len(fn) else 0.0
            score = blocked_f1(values, lab, grp, k)
            print(f"{k:4.0f} {cut:8.1f} {gap_below:10.1f} {gap_above:10.1f} "
                  f"{len(fp):3d} {len(fn):3d} {worst_fp:14.1f} {worst_fn:15.1f} "
                  f"{score:10.4f}")


if __name__ == "__main__":
    main()
