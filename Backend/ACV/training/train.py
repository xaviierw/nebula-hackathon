"""Fit the ACV model and write its artifacts.

Run under WSL if scikit-learn binaries are blocked on this machine -- see
Backend/Door/main.py:32-37 for the exact incantation.

Everything written into ../model/ must be reproducible from this script. The
API fingerprints those artifacts to version its prediction cache, so refitting
automatically invalidates stale cached results.
"""

from __future__ import annotations

from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1] / "model"


def main(argv=None) -> int:
    raise NotImplementedError("ACV training not written yet")


if __name__ == "__main__":
    raise SystemExit(main())
