"""Inference-time classifier: loads the portable model and labels cycles.

Deliberately free of any scikit-learn import. sklearn is used for *model
selection* during training (in WSL), but the shipped prediction path needs only
numpy and pandas, so the app runs natively on Windows under Smart App Control.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from core.scoring import ABNORMAL, NORMAL, Segment

MODEL_PATH = Path(__file__).resolve().parents[1] / "model" / "door_model.json"


class DoorClassifier:
    """Per-operation steady-state current threshold.

    Open and Close cycles have different current profiles, so each gets its own
    cut point. A cycle whose mid-travel mean current sits above its operation's
    threshold is flagged as abnormal resistance.
    """

    def __init__(self, spec: dict):
        if spec.get("model_type") != "operation_threshold":
            raise ValueError(f"unsupported model_type: {spec.get('model_type')}")
        self.spec = spec
        self.feature = spec["feature"]
        self.threshold_open = float(spec["threshold_open"])
        self.threshold_close = float(spec["threshold_close"])
        self.margin_open = float(spec.get("margin_open", 0.0))
        self.margin_close = float(spec.get("margin_close", 0.0))

    @classmethod
    def load(cls, path: str | Path = MODEL_PATH) -> "DoorClassifier":
        return cls(json.loads(Path(path).read_text()))

    DETAIL_COLUMNS = [
        "start_time", "end_time", "operation",
        "steady_current_mA", "threshold_mA", "prediction", "margin_ratio",
    ]

    def threshold_for(self, is_open: float) -> float:
        return self.threshold_open if is_open > 0.5 else self.threshold_close

    def _decide(self, row) -> dict:
        """The decision rule, defined once and used by every caller.

        Returns the verdict together with the numbers behind it, so the label
        shown to a user can never drift from the label that gets submitted.
        """
        is_open = row["is_open"] > 0.5
        cut = self.threshold_for(row["is_open"])
        gap = self.margin_open if is_open else self.margin_close
        value = float(row[self.feature])
        return {
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "operation": "Open" if is_open else "Close",
            "steady_current_mA": round(value, 1),
            "threshold_mA": round(cut, 1),
            "prediction": ABNORMAL if value > cut else NORMAL,
            # How far past the line, scaled by the class gap seen in training:
            # a readable confidence proxy for a non-technical user.
            "margin_ratio": round((value - cut) / max(abs(gap), 1.0), 3),
        }

    def predict(self, table: pd.DataFrame) -> list[str]:
        """Label each row of a feature table."""
        return [self._decide(row)["prediction"] for _, row in table.iterrows()]

    def explain(self, table: pd.DataFrame) -> pd.DataFrame:
        """Per-cycle detail for the app's results view."""
        rows = [self._decide(row) for _, row in table.iterrows()]
        return pd.DataFrame(rows, columns=self.DETAIL_COLUMNS)


def to_segments(table: pd.DataFrame, labels: list[str]) -> list[Segment]:
    """Pair a feature table with its predicted labels as scorer Segments."""
    return [
        Segment(row["start_time"], row["end_time"], label)
        for (_, row), label in zip(table.iterrows(), labels)
    ]
