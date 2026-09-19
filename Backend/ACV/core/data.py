"""Reading and validating an ACV input file."""

from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .errors import AcvInputError, AcvModelError

SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xls"}
CAR_COLUMN = re.compile(
    r"^car_(.+?)_(ambient_temp|indoor_temp|cooling_setpoint|running_mode|valid_status)$"
)
REQUIRED_CAR_FIELDS = {
    "indoor_temp",
    "cooling_setpoint",
    "running_mode",
    "valid_status",
}


def read_raw(
    source: str | Path | io.BytesIO,
    filename: str | None = None,
) -> pd.DataFrame:
    """Read an ACV file (Excel or CSV) from disk or memory."""
    suffix = Path(source).suffix.lower() if isinstance(source, (str, Path)) else Path(filename or "").suffix.lower()
    if suffix and suffix not in SUPPORTED_SUFFIXES:
        raise AcvInputError("Use an ACV operational export in CSV, XLSX or XLS format.")

    try:
        if suffix == ".xlsx":
            return pd.read_excel(source, engine="openpyxl")
        if suffix == ".xls":
            return pd.read_excel(source, engine="xlrd")
        if suffix == ".csv":
            return pd.read_csv(source)

        # Standalone callers may provide an unnamed byte stream. XLSX is a ZIP
        # container and legacy XLS uses the OLE compound-file signature.
        if hasattr(source, "read") and hasattr(source, "seek"):
            signature = source.read(8)
            source.seek(0)
            if signature.startswith(b"PK"):
                return pd.read_excel(source, engine="openpyxl")
            if signature.startswith(bytes.fromhex("D0CF11E0")):
                return pd.read_excel(source, engine="xlrd")
        return pd.read_csv(source)
    except ImportError as exc:
        raise AcvModelError(
            "ACV Excel support is not installed on the server. Reinstall Backend/requirements.txt."
        ) from exc
    except AcvInputError:
        raise
    except Exception as exc:
        raise AcvInputError(
            "Could not read the uploaded ACV file. Confirm that it is a valid, unencrypted CSV or Excel export."
        ) from exc


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
    """Validate normalized ACV columns before calculating a ranking."""
    if frame.empty:
        raise AcvInputError("The uploaded file contains no data rows.")

    if len(frame.columns) > 100:
        raise AcvInputError(
            f"Detected rich-telemetry format ({len(frame.columns)} columns). "
            "Please upload a standard 67-column ACV operational export."
        )

    duplicates = frame.columns[frame.columns.duplicated()].tolist()
    if duplicates:
        raise AcvInputError(
            "The ACV export contains duplicate sensor columns after normalization: "
            + ", ".join(map(str, duplicates))
        )

    fields_by_car: dict[str, set[str]] = {}
    for column in frame.columns:
        match = CAR_COLUMN.match(str(column))
        if match:
            fields_by_car.setdefault(match.group(1), set()).add(match.group(2))

    if len(fields_by_car) < 2:
        raise AcvInputError(
            "The ACV export must contain telemetry for at least two cars."
        )

    if not any("ambient_temp" in fields for fields in fields_by_car.values()):
        raise AcvInputError("The ACV export is missing outdoor temperature readings.")

    incomplete = {
        car_id: sorted(REQUIRED_CAR_FIELDS - fields)
        for car_id, fields in fields_by_car.items()
        if REQUIRED_CAR_FIELDS - fields
    }
    if incomplete:
        details = "; ".join(
            f"car {car_id}: {', '.join(fields)}"
            for car_id, fields in sorted(incomplete.items())
        )
        raise AcvInputError(f"The ACV export is missing required telemetry ({details}).")
