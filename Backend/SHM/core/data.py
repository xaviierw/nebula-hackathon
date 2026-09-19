"""Strict headerless recording reader; paths and in-memory streams are supported."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .errors import ShmInputError

OBSERVATIONS = 581120


def check_schema(frame: pd.DataFrame, expected_rows: int = OBSERVATIONS) -> None:
    if frame.shape != (expected_rows, 1):
        raise ShmInputError(
            f"Expected {expected_rows:,} observations in exactly one column without a header; "
            f"received {frame.shape[0]:,} rows and {frame.shape[1]} columns."
        )
    if not pd.api.types.is_numeric_dtype(frame.iloc[:, 0]) or not np.isfinite(frame.to_numpy()).all():
        raise ShmInputError("Stress observations must all be numeric and finite, without missing values or a header.")


def read_raw(path, expected_rows: int = OBSERVATIONS) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path, header=None, dtype="float64", skip_blank_lines=False)
    except (ValueError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ShmInputError(
            f"Expected {expected_rows:,} rows of finite numeric stress values in one column, "
            "without a header, missing values or extra columns."
        ) from exc
    check_schema(frame, expected_rows)
    return frame
