"""Score ACV predictions against training ground truth."""

from __future__ import annotations

import os
from pathlib import Path
import pandas as pd

from core.data import read_raw
from core.model import AcvModel
from prediction.predict import predict_file

HERE = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    print("\n--- Evaluating Training Set ---")
    train_dir = HERE / "training" / "Train"
    if not train_dir.exists():
        train_dir = HERE / "Train"

    labels_file = HERE / "training" / "Train_Labels.csv"
    if not labels_file.exists():
        labels_file = HERE / "Train_Labels.csv"

    labels_df = pd.DataFrame()
    if labels_file.exists():
        labels_df = pd.read_csv(labels_file)

    model = AcvModel.load()
    files = sorted(train_dir.glob("acv_case_*.xlsx"))

    passed, total = 0, 0
    for filepath in files:
        filename = filepath.name
        try:
            raw_df = read_raw(filepath)
            res = predict_file(raw_df, model)
            predicted_fault = res["ranked_cars"][0]

            actual_fault = "Unknown"
            if not labels_df.empty and 'filename' in labels_df.columns:
                match = labels_df[labels_df['filename'] == filename]
                if not match.empty:
                    actual_fault = str(match['faulty_car'].values[0]).zfill(2)

            is_pass = predicted_fault == actual_fault
            if is_pass:
                passed += 1
            total += 1

            status = "PASS" if is_pass else ("FAIL" if actual_fault != "Unknown" else "UNVERIFIED")
            rank_str = "|".join(res["ranked_cars"])
            print(f"{filename} -> Predicted: {predicted_fault} | Actual: {actual_fault} | {status} | Full Rank: {rank_str}")
        except Exception as e:
            print(f"{filename} -> Skipped ({e})")

    print(f"\nAccuracy: {passed}/{total} verified correct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())