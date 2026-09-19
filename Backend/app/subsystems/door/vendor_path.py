"""Make Backend/Door importable without touching a line of it.

Backend/Door has no package root. Its modules import each other absolutely --
`from core.data import ...`, `from prediction.predict import ...` -- and rely
on Backend/Door itself being on sys.path. Backend/Door/main.py:139 and
Backend/Door/predict.py:17 both do this for the CLI; this is the API's copy.
"""

from __future__ import annotations

import sys
from pathlib import Path

DOOR_ROOT = Path(__file__).resolve().parents[3] / "Door"


def ensure_door_importable() -> None:
    """APPEND Backend/Door to sys.path. Append, never insert(0).

    Backend/Door/main.py inserts at position 0, which is right for the CLI and
    wrong here: at position 0, `Backend/Door/main.py` would shadow this
    project's own `Backend/main.py` for any `import main`, and Door's `model/`,
    `output/`, `training/` and `audit/` folders would all become importable
    top-level namespace packages ahead of site-packages.

    Appending is safe because no installed distribution provides a top-level
    `core` or `prediction` module. That is an assumption, so DoorRunner.load()
    asserts it rather than trusting it -- see runner.py.
    """
    path = str(DOOR_ROOT)
    if path not in sys.path:
        sys.path.append(path)
