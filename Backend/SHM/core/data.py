"""Reading and validating a SHM input file.

Mirrors Backend/Door/core/data.py. Keep reading separate from parsing so a
caller can validate the schema first and report a readable error, rather than
failing inside a parser on a file that was never a SHM recording.
"""

from __future__ import annotations

import pandas as pd

from .errors import ShmInputError

# TODO: the exact column names from the SHM info kit in
# Backend/03_References/SHM/. Door keeps its equivalents in core/data.py:19-25.
REQUIRED_COLUMNS: list[str] = []


def read_raw(path) -> pd.DataFrame:
    """Read a SHM file without touching its contents.

    `path` may be a path OR a file-like object -- the API passes an
    io.BytesIO of the upload, and never writes it to disk.
    """
    return pd.read_csv(path)


def check_schema(frame: pd.DataFrame) -> None:
    """Fail early and legibly if this is not a SHM recording."""
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ShmInputError(
            "Input file is missing required column(s):\n"
            + "".join(f"  - {c}\n" for c in missing)
            + "\nFound these columns instead:\n"
            + "".join(f"  - {c}\n" for c in frame.columns)
            + "\nExpected a SHM recording."
        )
    if frame.empty:
        raise ShmInputError("Input file contains no data rows.")
