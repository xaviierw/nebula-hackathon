"""Door subsystem -- single entry point for every stage of the pipeline.

    python main.py train                          fit and select the model
    python main.py predict --input Test.csv       classify a stream
    python main.py evaluate                       score on the sealed holdout
    python main.py verify                         check a submission's format
    python main.py check                          run the correctness tests

Layout:
    core/        shared by both stages -- loading, segmentation, features,
                 the classifier, and the official metric
    training/    fits the model. Needs scikit-learn, so it runs under WSL
                 (Smart App Control blocks sklearn's binaries on Windows)
    prediction/  produces and validates submissions. numpy and pandas only,
                 so it runs natively on Windows

Everything except `train` runs on Windows.
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE.parent / "02_Datasets" / "Door" / "Test.csv"
DEFAULT_OUTPUT = HERE / "output" / "door_predictions.csv"
DEFAULT_DETAIL = HERE / "output" / "door_detail.csv"

SKLEARN_HINT = """
This stage needs scikit-learn, which Windows Smart App Control blocks.
Run it under WSL instead:

  wsl -d Ubuntu -- bash -lc "cd {path}; python3 main.py train"
"""


def _run_script(relative: str, argv: list[str]) -> int:
    """Execute a stage script with the given argv, as if run directly."""
    saved = sys.argv
    sys.argv = [str(HERE / relative), *argv]
    try:
        runpy.run_path(str(HERE / relative), run_name="__main__")
        return 0
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        # SystemExit carrying a message: show it the way Python normally would.
        print(code, file=sys.stderr)
        return 1
    finally:
        sys.argv = saved


def cmd_train(args: argparse.Namespace) -> int:
    try:
        from training.train import main as train_main
    except ImportError as exc:
        if "sklearn" in str(exc) or "Application Control" in str(exc):
            posix = HERE.as_posix().replace("C:/", "/mnt/c/")
            print(SKLEARN_HINT.format(path=posix), file=sys.stderr)
            return 1
        raise
    train_main()
    return 0


def cmd_predict(args: argparse.Namespace) -> int:
    argv = ["--input", str(args.input), "--output", str(args.output)]
    if args.detail:
        argv += ["--detail", str(args.detail)]
    if args.model:
        argv += ["--model", str(args.model)]
    if args.quiet:
        argv.append("--quiet")
    return _run_script("prediction/predict.py", argv)


def cmd_evaluate(args: argparse.Namespace) -> int:
    return _run_script("training/evaluate.py", [])


def cmd_verify(args: argparse.Namespace) -> int:
    return _run_script("prediction/verify_submission.py", ["--file", str(args.file)])


def cmd_check(args: argparse.Namespace) -> int:
    failures = 0
    for name, script in (
        ("metric correctness", "training/test_metrics.py"),
        ("segmentation accuracy", "training/validate_segmentation.py"),
    ):
        print(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
        failures += _run_script(script, []) != 0
    print(f"\n{'=' * 60}")
    print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Door subsystem: detect and classify door open/close cycles.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run 'main.py <command> --help' for a command's own options.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("train", help="fit and select the model (needs WSL)")
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("predict", help="classify a continuous stream")
    p.add_argument("--input", default=DEFAULT_INPUT, help="stream CSV to classify")
    p.add_argument("--output", default=DEFAULT_OUTPUT, help="predictions CSV to write")
    p.add_argument("--detail", default=DEFAULT_DETAIL, help="per-cycle detail CSV")
    p.add_argument("--model", default=None, help="trained model JSON")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_predict)

    p = sub.add_parser("evaluate", help="score the pipeline on the sealed holdout")
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("verify", help="check a submission file's format")
    p.add_argument("--file", default=DEFAULT_OUTPUT, help="predictions CSV to check")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("check", help="run the metric and segmentation tests")
    p.set_defaults(func=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(HERE))  # make core/ training/ prediction/ importable
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
