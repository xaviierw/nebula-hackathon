"""Adapter between the Rail Corrugation model and the shared API."""

from __future__ import annotations

import hashlib
import importlib
import logging
from types import ModuleType

from Rail_Corrugation.core.errors import RailInputError, RailModelError

from ...schemas.rail import RailResult
from ..base import SubsystemRunner

log = logging.getLogger(__name__)

PIPELINE_REVISION = "rail-1"


class RailRunner(SubsystemRunner):
    id = "rail-corrugation"
    name = "Rail Corrugation"
    upload_mode = "per-file"
    response_model = RailResult

    def load(self) -> None:
        """Load and validate Rail lazily so missing dependencies affect Rail only."""
        try:
            predictor = importlib.import_module("Rail_Corrugation.prediction.predict")
            bundle = predictor.load_rail_model()
            model_path = predictor.DEFAULT_MODEL_PATH
            fingerprint = hashlib.sha256(model_path.read_bytes()).hexdigest()[:12]
        except Exception as exc:
            self.available = False
            self.unavailable_reason = (
                "The Rail Corrugation model is installed incorrectly: "
                f"{exc}"
            )
            self.model_version = "unavailable"
            log.warning("Rail Corrugation unavailable: %s", exc)
            return

        self._predictor: ModuleType = predictor
        self._bundle = bundle
        self.model_version = f"{PIPELINE_REVISION}:{fingerprint}"
        self.unavailable_reason = None
        self.available = True
        log.info("Rail Corrugation ready (model_version=%s)", self.model_version)

    def run(self, raw: bytes, filename: str) -> dict:
        try:
            analysis = self._predictor.analyse_bytes(raw, filename, self._bundle)
        except ValueError as exc:
            # predictor.py reserves ValueError for user-correctable CSV faults;
            # the bundle was already loaded and validated during startup.
            raise RailInputError(str(exc)) from exc
        except Exception as exc:
            raise RailModelError(
                "The Rail Corrugation model could not analyse this recording."
            ) from exc

        # file_id belongs to the submission/export layer, not the cached model
        # payload. The shared batch route already returns each upload filename.
        return {
            "prediction": analysis["prediction"],
            "evidence": analysis["evidence"],
        }
