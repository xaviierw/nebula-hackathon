"""Portable deployed physics model; no fitting or training imports."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import rainflow

from .data import OBSERVATIONS
from .errors import ShmInputError, ShmModelError
from .features import CACHE_VERSION, EXPONENTS, logq_column

MODEL_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "model.json"
PIPELINE_REVISION = "shm-1"


class ShmModel:
    @classmethod
    def load(cls, path=MODEL_PATH):
        try:
            raw = Path(path).read_bytes()
            artifact = json.loads(raw)
            if type(artifact["version"]) is not int or artifact["version"] != 1:
                raise ValueError("Unsupported SHM artifact version")
            if artifact["feature_version"] != CACHE_VERSION:
                raise ValueError("Model/extractor version mismatch")
            if artifact["dependencies"]["rainflow"] != rainflow.__version__ or rainflow.__version__ != "3.2.0":
                raise ValueError("SHM requires rainflow 3.2.0")
            if artifact["observations"] != OBSERVATIONS:
                raise ValueError("Unexpected model recording length")
            candidate = artifact["model"]["candidate"]
            state = artifact["model"]["state"]
            if (set(candidate) != {"family", "m", "beta", "alpha"}
                    or candidate["family"] != "physics" or candidate["m"] not in EXPONENTS
                    or candidate["beta"] != 1.0 or candidate["alpha"] != 10.0):
                raise ValueError("Unsupported SHM model configuration; expected a calibrated physics model")
            if (set(state) != {"log_scale"} or type(state["log_scale"]) not in (int, float)
                    or not math.isfinite(state["log_scale"])):
                raise ValueError("Invalid finite log_scale in SHM artifact")
            model = cls()
            model.exponent = float(candidate["m"])
            model.log_scale = float(state["log_scale"])
            model.observations = OBSERVATIONS
            model.model_id = hashlib.sha256(raw).hexdigest()
            model.model_version = f"{PIPELINE_REVISION}:{model.model_id}"
            return model
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ShmModelError(f"Cannot load the deployed SHM artifact: {exc}") from exc

    def predict(self, features: dict) -> float:
        try:
            log_prediction = self.log_scale + features[logq_column(self.exponent)]
        except (KeyError, TypeError) as exc:
            raise ShmModelError("SHM features are incompatible with the deployed model.") from exc
        with np.errstate(over="ignore", under="ignore"):
            prediction = float(np.exp(log_prediction))
        if not math.isfinite(prediction) or prediction <= 0:
            raise ShmInputError("This recording's fatigue damage is outside the supported positive finite numeric range.")
        return prediction
