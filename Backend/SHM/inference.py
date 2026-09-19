"""Shared, label-free inference for the web app and command-line prediction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from data import CACHE_VERSION, OBSERVATIONS, extract_signal, read_signal, require
from models import FittedModel, candidates

DEFAULT_MODEL = Path(__file__).resolve().parent / "artifacts" / "model.json"
MAX_UPLOAD_BYTES = 16 * 1024 * 1024


def validate_filename(name):
    require(isinstance(name, str) and 0 < len(name) <= 255, "A CSV filename is required.")
    require(not any(c in name for c in '/\\\r\n\x00') and not any(ord(c) < 32 for c in name),
            "Use a filename without paths or control characters.")
    require(name.lower().endswith('.csv'), "Please upload a .csv stress recording.")
    return name


class Predictor:
    def __init__(self, model_path=DEFAULT_MODEL):
        raw = Path(model_path).read_bytes()
        artifact = json.loads(raw)
        require(artifact['version'] == 1, "Unsupported SHM artifact version")
        require(artifact['feature_version'] == CACHE_VERSION, "Model/extractor version mismatch")
        require(artifact['observations'] == OBSERVATIONS, "Unexpected model recording length")
        self.model = FittedModel.from_dict(artifact['model'])
        require(self.model.candidate in candidates(True), "Unsupported SHM model configuration")
        self.model_id = hashlib.sha256(raw).hexdigest()
        self.observations = artifact['observations']

    def predict(self, raw: bytes, filename: str):
        validate_filename(filename)
        require(0 < len(raw) <= MAX_UPLOAD_BYTES, "Upload a nonempty CSV no larger than 16 MiB.")
        try:
            signal = read_signal(raw, self.observations)
        except (ValueError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
            raise ValueError(
                f"Expected {self.observations:,} rows of finite numeric stress values in one column, "
                "without a header, missing values or extra columns."
            ) from exc
        features = extract_signal(signal)
        prediction = float(self.model.predict(pd.DataFrame([features]))[0])
        return dict(file_id=filename, prediction=prediction, observations=len(signal),
                    weighted_cycle_count=features['cycle_count'], model_id=self.model_id)
