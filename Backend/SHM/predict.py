"""Portable inference entry point; supports --input/--output without labels."""
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "SHM"

from .main import main

if __name__ == "__main__":
    sys.argv.insert(1, "predict")
    main()
