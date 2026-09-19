"""Rail Corrugation subsystem CLI.

    python main.py train
    python main.py predict --input <file>
    python main.py evaluate

Mirrors Backend/Door/main.py. The API does NOT call this file -- it imports
prediction/predict.py directly. Keep the two paths equivalent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def cmd_train(args) -> int:
    from training.train import main as train_main

    return train_main([])


def cmd_predict(args) -> int:
    raise NotImplementedError("Rail Corrugation predict CLI not written yet")


def cmd_evaluate(args) -> int:
    from training.evaluate import main as eval_main

    return eval_main([])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Rail Corrugation subsystem: Multi-class classification -- Normal / Side I / Side II corrugation.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("train", help="Fit the model and write ./model artifacts")

    p = sub.add_parser("predict", help="Score a file and write a submission CSV")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", type=Path, default=HERE / "output" / "rail_predictions.csv")

    sub.add_parser("evaluate", help="Score predictions against held-out labels")

    args = parser.parse_args(argv)
    handlers = {"train": cmd_train, "predict": cmd_predict, "evaluate": cmd_evaluate}
    return handlers[args.command](args)


if __name__ == "__main__":
    # Same shim as Backend/Door/main.py:139 -- core/ and prediction/ import
    # each other absolutely, so this directory must be on sys.path.
    sys.path.insert(0, str(HERE))
    raise SystemExit(main())
