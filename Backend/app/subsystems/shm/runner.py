"""In-memory adapter for the deployed SHM artifact."""
from __future__ import annotations

import io

from SHM.core.data import read_raw
from SHM.core.errors import ShmModelError
from SHM.core.model import MODEL_PATH, ShmModel
from SHM.prediction.predict import predict_file

from ...schemas.shm import ShmResult
from ..base import SubsystemRunner


class ShmRunner(SubsystemRunner):
    id = "shm"
    name = "SHM"
    upload_mode = "per-file"
    response_model = ShmResult

    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path
        self._model = None

    def load(self) -> None:
        self.available = False
        self.model_version = "unavailable"
        self._model = None
        try:
            self._model = ShmModel.load(self.model_path)
        except ShmModelError as exc:
            self.unavailable_reason = str(exc)
            return
        self.model_version = self._model.model_version
        self.unavailable_reason = None
        self.available = True

    def run(self, raw: bytes, filename: str) -> dict:
        if self._model is None:
            raise ShmModelError(self.unavailable_reason or "SHM model is not loaded.")
        # Filename is request metadata, never part of a content-cached payload.
        return predict_file(read_raw(io.BytesIO(raw)), self._model)
