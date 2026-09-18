"""Audit item 6 (substitute): leave-one-time-block-out cross-validation.

The requested leave-one-DOOR-out test is impossible: neither Train.csv nor
Test.csv carries a Car Type / Car Number / Door Number column, despite
'Door Data Headers.md' listing them. There is no door identifier to group on.

The closest available grouping is TEMPORAL. Cycles are assigned to contiguous
time blocks and each block is held out whole. This tests the property that
leave-one-door-out would have tested -- does the model generalise to an unseen
operating session, or has it memorised conditions shared within a session --
without claiming to be a per-door test.

Read-only: imports the real training code, writes nothing.

    python audit/grouped_cv.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from sklearn.metrics import f1_score, recall_score

from core.data import DATA_DIR, chronological_split, find_cycles, load_stream, load_truth
from core.features import FEATURE_COLUMNS, build_table
from core.scoring import ABNORMAL
from training.train import build_candidates

N_BLOCKS = 5


def evaluate(name: str, X, y, groups) -> None:
    print(f"\n### {name}")
    print(f"{'block':>6s} {'n':>4s} {'norm/abn':>9s} {'macro-F1':>9s} "
          f"{'abnormal recall':>16s}")
    print("-" * 52)
    f1s, recalls = [], []
    for block in sorted(set(groups)):
        test_mask = groups == block
        train_mask = ~test_mask
        y_train, y_test = y[train_mask], y[test_mask]
        if len(set(y_train)) < 2 or len(set(y_test)) < 1:
            print(f"{block:6d} -- skipped, a class is missing from this split")
            continue
        model = build_candidates()[name]
        model.fit(X[train_mask], y_train)
        predicted = model.predict(X[test_mask])
        macro = f1_score(y_test, predicted, average="macro")
        n_abnormal = int((y_test == ABNORMAL).sum())
        rec = (recall_score(y_test, predicted, pos_label=ABNORMAL)
               if n_abnormal else float("nan"))
        f1s.append(macro)
        if n_abnormal:
            recalls.append(rec)
        print(f"{block:6d} {test_mask.sum():4d} "
              f"{int((y_test != ABNORMAL).sum()):4d}/{n_abnormal:<4d} "
              f"{macro:9.4f} {rec:16.4f}")
    print("-" * 52)
    print(f"{'mean':>6s} {'':4s} {'':9s} {np.mean(f1s):9.4f} "
          f"{np.mean(recalls):16.4f}")


def main() -> None:
    stream = load_stream(DATA_DIR / "Train.csv")
    truth = load_truth(DATA_DIR / "Train_Segments_Answer.csv")
    fit_frame, fit_truth, _, _ = chronological_split(stream, truth)
    table = build_table(fit_frame, find_cycles(fit_frame))
    X = table[FEATURE_COLUMNS]
    y = np.array([s.label for s in fit_truth])

    # Contiguous temporal blocks: cycles stay in chronological order, so an
    # equal-width split by index is also a split by wall-clock time.
    groups = np.minimum((np.arange(len(y)) * N_BLOCKS) // len(y), N_BLOCKS - 1)

    print(f"Leave-one-time-block-out: {len(y)} cycles, {N_BLOCKS} contiguous blocks")
    print("(substitute for leave-one-door-out -- no door identifier exists)\n")
    for block in range(N_BLOCKS):
        mask = groups == block
        span = table.loc[mask, "start_time"]
        print(f"  block {block}: {mask.sum():2d} cycles  "
              f"{span.min()} .. {span.max()}")

    for name in build_candidates():
        evaluate(name, X, y, groups)


if __name__ == "__main__":
    main()
