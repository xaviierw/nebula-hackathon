"""Inference entry point, kept at the folder root where the brief expects it.

The Door info kit (Section 5) specifies a `predict.py` taking --input/--output.
The implementation lives in prediction/predict.py; this is the stable filename
that scripts, the app, and the graders can rely on.

    python predict.py --input Test.csv --output door_predictions.csv

Equivalent to `python main.py predict`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prediction.predict import main  # noqa: E402  (needs the path set first)

if __name__ == "__main__":
    sys.exit(main())
