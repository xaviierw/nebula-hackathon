# Handles string mapping, sanitization and data preprocessing
import pandas as pd
import numpy as np
import re

def standardize_column_names(df):
    """Maps exact variant strings to unified internal variables."""
    new_cols = []
    for col in df.columns:
        col_str = str(col)
        new_col = col_str
        match = re.search(r'(0[1-8])', col_str)
        if match:
            car_id = match.group(1)
            lower_col = col_str.lower()

            if "outdoor average" in lower_col or "outside temperature" in lower_col:
                new_col = f"car_{car_id}_ambient_temp"
            elif "indoor average" in lower_col or "indoor" in lower_col:
                new_col = f"car_{car_id}_indoor_temp"
            elif "control temperature (cooling)" in lower_col or "cooling control" in lower_col:
                new_col = f"car_{car_id}_cooling_setpoint"
            # NEW: running mode — needed to gate out Stop/Ventilation/Emergency rows,
            # which were previously included in the shortfall calculation unfiltered.
            elif "running mode" in lower_col:
                new_col = f"car_{car_id}_running_mode"
            elif "information valid" in lower_col or "information-valid" in lower_col:
                new_col = f"car_{car_id}_valid_status"

        new_cols.append(new_col)
    df.columns = new_cols
    return df

def sanitize_sensor_data(df):
    """Strips out 'Invalid' text strings and coerces target columns to numeric floats."""
    df = df.replace(['Invalid', 'invalid', 'INVALID'], np.nan)
    for col in df.columns:
        if col.endswith('_temp') or col.endswith('_setpoint'):
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

def calculate_train_ambient_ref(df):
    """Isolates all ambient temperature columns and calculates a single cross-car median.
    Uses whichever cars have a valid reading at each timestamp — some file variants only
    populate the outdoor sensor on the end cars (01/08), so requiring every car's own
    sensor would silently drop most rows."""
    ambient_cols = [col for col in df.columns if '_ambient_temp' in col]
    df['train_ambient_ref'] = df[ambient_cols].median(axis=1)
    return df