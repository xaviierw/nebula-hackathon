"""Score ACV predictions against training ground truth."""

from __future__ import annotations

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

    if not train_dir.exists():
        print(f"Training recordings were not found at {train_dir}.")
        return 1
    if not labels_file.exists():
        print(f"Training labels were not found at {labels_file}.")
        return 1

    labels_df = pd.read_csv(labels_file)
    required = {"filename", "faulty_car"}
    if not required.issubset(labels_df.columns):
        print("Train_Labels.csv must contain filename and faulty_car columns.")
        return 1

    model = AcvModel.load()
    files = sorted(train_dir.glob("acv_case_*.xlsx"))
    if not files:
        print(f"No acv_case_*.xlsx recordings were found in {train_dir}.")
        return 1

    passed, total = 0, 0
    for filepath in files:
        filename = filepath.name
        try:
            raw_df = read_raw(filepath)
            res = predict_file(raw_df, model)
            predicted_fault = res["ranked_cars"][0]

            match = labels_df[labels_df["filename"] == filename]
            if match.empty:
                print(f"{filename} -> Skipped (no matching label)")
                continue
            actual_fault = str(match["faulty_car"].values[0]).zfill(2)

            is_pass = predicted_fault == actual_fault
            if is_pass:
                passed += 1
            total += 1

            status = "PASS" if is_pass else "FAIL"
            rank_str = "|".join(res["ranked_cars"])
            print(f"{filename} -> Predicted: {predicted_fault} | Actual: {actual_fault} | {status} | Full Rank: {rank_str}")
        except Exception as e:
            print(f"{filename} -> Skipped ({e})")

    if total == 0:
        print("No labelled recordings could be evaluated.")
        return 1
    print(f"\nTop-ranked accuracy: {passed}/{total} verified correct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
