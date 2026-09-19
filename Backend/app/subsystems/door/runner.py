"""Door runner: adapts Backend/Door's prediction pipeline to the API.

This is the worked reference for the other three subsystems. The whole job is
to turn `bytes` into a JSON-ready dict, reusing the subsystem's own code and
its own error types.
"""

from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path

import pandas as pd

from ...schemas.door import DoorResult
from ..base import SubsystemRunner
from .vendor_path import DOOR_ROOT, ensure_door_importable

ensure_door_importable()

from core.classifier import MODEL_PATH, DoorClassifier  # noqa: E402
from core.data import parse_times, read_raw  # noqa: E402
from core.errors import DoorInputError  # noqa: E402
from core.scoring import format_time  # noqa: E402
from prediction.predict import check_schema, load_reference, predict_stream  # noqa: E402

log = logging.getLogger(__name__)

# Bump by hand only if predict_stream's output contract changes in a way the
# model artifacts do not reflect. Routine retraining is picked up automatically
# by the artifact fingerprint below.
PIPELINE_REVISION = "door-1"

REFERENCE_PATH = DOOR_ROOT / "model" / "door_reference.json"


class DoorRunner(SubsystemRunner):
    id = "door"
    name = "Door"
    upload_mode = "stream"  # one continuous recording, many result rows
    response_model = DoorResult

    def load(self) -> None:
        # Append-to-sys.path is safe but shadowable. Verify rather than trust:
        # a wrong `core` would produce confidently wrong predictions, which is
        # far worse than a crash.
        import core.classifier as _cc

        resolved = Path(_cc.__file__).resolve()
        if not resolved.is_relative_to(DOOR_ROOT):
            raise RuntimeError(
                f"'core' resolved to {resolved}, not {DOOR_ROOT}. "
                "Something else on sys.path provides a top-level 'core' package."
            )

        if not MODEL_PATH.exists():
            self.available = False
            self.unavailable_reason = (
                "The Door model has not been built on this machine.\n"
                "Run `python Backend/Door/main.py train` (under WSL) to create "
                "Backend/Door/model/door_model.json."
            )
            log.warning("Door unavailable: %s missing", MODEL_PATH)
            return

        self._classifier = DoorClassifier.load(MODEL_PATH)
        # Optional. When absent, check_sampling and check_durations both
        # short-circuit and warnings is always [] -- a known, correct
        # degradation, not a bug. See Backend/README.md.
        self._reference = load_reference()
        if self._reference is None:
            log.info("door_reference.json absent; warnings will be empty")

        self.model_version = f"{PIPELINE_REVISION}:{self._fingerprint()}"
        self.available = True
        log.info("Door ready (model_version=%s)", self.model_version)

    def _fingerprint(self) -> str:
        """Hash the artifacts so a retrain invalidates the cache by itself.

        Because model_version is part of the cache key, refitting the model
        changes every key -- no manual version bump, no purge script, and old
        results stay readable for history.
        """
        h = hashlib.sha256()
        h.update(MODEL_PATH.read_bytes())
        if REFERENCE_PATH.exists():
            h.update(REFERENCE_PATH.read_bytes())
        return h.hexdigest()[:12]

    def run(self, raw: bytes, filename: str) -> dict:
        """Re-implements load_inputs (Backend/Door/prediction/predict.py:200)
        minus its two path .exists() checks.

        load_inputs takes a Path and cannot serve an upload, but every error
        type and message it raises is preserved here verbatim, so the
        DoorInputError / DoorModelError contract still holds.
        """
        try:
            frame = read_raw(io.BytesIO(raw))
        except Exception as exc:  # malformed CSV, wrong encoding, not a CSV
            raise DoorInputError(
                f"Could not read '{filename}' as a CSV file: {exc}"
            ) from exc

        check_schema(frame)  # validate before parsing, so errors stay readable

        try:
            frame = parse_times(frame)
        except ValueError as exc:
            raise DoorInputError(str(exc)) from exc

        _submission, detail, _features, warnings = predict_stream(
            frame, self._classifier, self._reference
        )
        return {"detail": _rows(detail), "warnings": warnings}


def _rows(detail: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-ready rows.

    predict_stream returns an empty frame with no columns when it finds no
    cycles (predict.py:186); the frontend renders a dedicated empty state for
    that, so it is a valid result, not an error.

    The explicit int()/float()/str() casts are not decoration. iterrows()
    yields numpy scalars, and np.int64 is not a subclass of int -- Pydantic
    rejects it. Casting also keeps this working across the pandas 2.x/3.x
    split that Door/requirements.txt supports.
    """
    if detail.empty:
        return []
    return [
        {
            # format_time mirrors what predict.py:268-269 writes to CSV: the
            # dataset's native format, not ISO.
            "start_time": format_time(row["start_time"]),
            "end_time": format_time(row["end_time"]),
            "start_row": int(row["start_row"]),
            "end_row": int(row["end_row"]),
            "operation": str(row["operation"]),
            "steady_current_mA": float(row["steady_current_mA"]),
            "threshold_mA": float(row["threshold_mA"]),
            "prediction": str(row["prediction"]),
            "margin_ratio": float(row["margin_ratio"]),
        }
        for _, row in detail.iterrows()
    ]
