"""Pure one-recording inference shared by the API and command line."""
from __future__ import annotations

import pandas as pd

from ..core.data import check_schema
from ..core.features import extract_signal
from ..core.model import ShmModel


def predict_file(frame: pd.DataFrame, model: ShmModel, reference=None) -> dict:
    check_schema(frame, model.observations)
    features = extract_signal(frame.iloc[:, 0].to_numpy(), exponents=(model.exponent,))
    return {
        "prediction": model.predict(features),
        "observations": int(features["n"]),
        "weighted_cycle_count": float(features["cycle_count"]),
        "model_id": model.model_id,
        "model_version": model.model_version,
        "interval": None,
        "warnings": [],
    }
