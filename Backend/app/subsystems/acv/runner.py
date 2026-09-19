"""API adapter for the ACV prediction pipeline."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from ACV.core.data import read_raw
from ACV.core.model import AcvModel
from ACV.prediction.predict import predict_file
from ...schemas.acv import AcvResult
from ..base import SubsystemRunner

# Keep the API and `Backend/ACV/main.py predict` on the same model artifact.
# The current training command writes the model to Backend/model.
MODEL_PATH = Path(__file__).resolve().parents[3] / "model" / "acv_model.json"


class AcvRunner(SubsystemRunner):
    id = "acv"
    name = "ACV"
    upload_mode = "per-file"
    response_model = AcvResult

    def load(self) -> None:
        if not MODEL_PATH.exists():
            self.available = False
            self.unavailable_reason = (
                "The ACV model has not been built yet. "
                "Run `python Backend/ACV/main.py train` first."
            )
            return

        self._model = AcvModel.load(MODEL_PATH)
        # Bump the pipeline revision whenever feature or ranking semantics
        # change so Firestore cannot serve stale cached predictions.
        self.model_version = f"acv-2:{self._fingerprint()}"
        self.available = True
        self.unavailable_reason = None

    def run(self, raw: bytes, filename: str) -> dict:
        frame = read_raw(io.BytesIO(raw), filename)
        return predict_file(frame, self._model)

    @staticmethod
    def _fingerprint() -> str:
        return hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()[:12]
