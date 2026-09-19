"""ACV subsystem CLI.

    python main.py train
    python main.py predict --input <file>
    python main.py evaluate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from core.data import read_raw
from core.model import AcvModel
from prediction.predict import predict_file


def cmd_train(args) -> int:
    from training.train import main as train_main
    return train_main([])


def cmd_predict(args) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found at {input_path}")
        return 1

    model = AcvModel.load()
    raw_df = read_raw(input_path)
    result = predict_file(raw_df, model)

    ranked_str = "|".join(result["ranked_cars"])
    print(f"Predictions for {input_path.name}: {ranked_str}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    submission_df = pd.DataFrame({
        "file_id": [input_path.name],
        "ranked_cars": [ranked_str]
    })
    submission_df.to_csv(output_path, index=False)
    print(f"Saved submission output to: {output_path}")
    return 0


def cmd_evaluate(args) -> int:
    from training.evaluate import main as eval_main
    return eval_main([])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ACV subsystem: Fault diagnosis / localisation.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("train", help="Fit the model and write ./model artifacts")

    p = sub.add_parser("predict", help="Score a file and write a submission CSV")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", type=Path, default=HERE / "output" / "acv_predictions.csv")

    sub.add_parser("evaluate", help="Score predictions against held-out labels")

    args = parser.parse_args(argv)
    handlers = {"train": cmd_train, "predict": cmd_predict, "evaluate": cmd_evaluate}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())