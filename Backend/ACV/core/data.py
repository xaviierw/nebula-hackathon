"""Reading and validating an ACV input file."""

from __future__ import annotations

import io
import re
from pathlib import Path
import numpy as np
import pandas as pd

from .errors import AcvInputError


def read_raw(path: str | Path | io.BytesIO) -> pd.DataFrame:
    """Read an ACV file (Excel or CSV) from disk or memory."""
    try:
        # Check if it's a file path string/Path
        if isinstance(path, (str, Path)):
            p = Path(path)
            if p.suffix.lower() in [".xlsx", ".xls"]:
                return pd.read_excel(p)
            return pd.read_csv(p)
        
        # In-memory file-like object (e.g. from FastAPI UploadFile)
        try:
            return pd.read_excel(path)
        except Exception:
            if hasattr(path, "seek"):
                path.seek(0)
            return pd.read_csv(path)
    except Exception as e:
        raise AcvInputError(f"Could not read the uploaded file: {e}")


def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Maps inconsistent variant strings across files to standard names."""
    new_cols = []
    for col in df.columns:
        col_str = str(col)
        new_col = col_str
        match = re.search(r"(?i)\bcar\s+(.+?)\s+-\s+", col_str)
        if not match:
            # Support already compact headers such as car_03_indoor_temp.
            match = re.search(r"(?i)^car_(.+?)_(?:ambient_temp|indoor_temp|cooling_setpoint|running_mode|valid_status)$", col_str)
        if match:
            car_id = match.group(1).strip()
            lower_col = col_str.lower()
            if "outdoor average" in lower_col or "outside temperature" in lower_col:
                new_col = f"car_{car_id}_ambient_temp"
            elif "indoor average" in lower_col or "indoor" in lower_col:
                new_col = f"car_{car_id}_indoor_temp"
            elif "control temperature (cooling)" in lower_col or "cooling control" in lower_col:
                new_col = f"car_{car_id}_cooling_setpoint"
            elif "running mode" in lower_col:
                new_col = f"car_{car_id}_running_mode"
            elif "information valid" in lower_col or "information-valid" in lower_col:
                new_col = f"car_{car_id}_valid_status"
        new_cols.append(new_col)
    df.columns = new_cols
    return df


def sanitize_sensor_data(df: pd.DataFrame) -> pd.DataFrame:
    """Strips out 'Invalid' text strings and coerces target columns to numeric floats."""
    df = df.replace(['Invalid', 'invalid', 'INVALID'], np.nan)
    for col in df.columns:
        if col.endswith('_temp') or col.endswith('_setpoint'):
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def check_schema(frame: pd.DataFrame) -> None:
    """Validates the schema, failing early and legibly."""
    if frame.empty:
        raise AcvInputError("The uploaded file contains no data rows.")
    
    if len(frame.columns) > 100:
        raise AcvInputError(
            f"Detected rich-telemetry format ({len(frame.columns)} columns). "
            "Please upload a standard 67-column ACV operational export."
        )

    # Verify that at least one indoor temp column exists
    indoor_cols = [c for c in frame.columns if "indoor" in str(c).lower()]
    if not indoor_cols:
        raise AcvInputError(
            "Input file is missing required car indoor temperature columns.\n"
            "Expected standard ACV telemetry with per-car readings."
        )