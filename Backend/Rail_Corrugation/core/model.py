"""The Rail Corrugation model: load and predict.

Inference should avoid importing scikit-learn where practical. Door exports a
plain-JSON threshold spec so its prediction path is sklearn-free, which is why
the API can run natively on Windows while training runs under WSL (see
Backend/Door/main.py:32-37). If your model genuinely needs sklearn at
inference time, say so in this subsystem README so the constraint is visible.
"""

from __future__ import annotations

from pathlib import Path

from .errors import RailModelError

MODEL_PATH = Path(__file__).resolve().parents[1] / "model" / "rail_model.json"


class RailModel:
    @classmethod
    def load(cls, path=MODEL_PATH):
        path = Path(path)
        if not path.exists():
            raise RailModelError(
                f"Model file not found: {path}\n"
                "Run `python main.py train` in this directory first."
            )
        raise NotImplementedError("Rail Corrugation model loading not written yet")

    def predict(self, features):
        raise NotImplementedError("Rail Corrugation prediction not written yet")
