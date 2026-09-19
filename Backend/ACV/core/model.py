"""The ACV model: configuration and heuristic ranking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pandas as pd

from .errors import AcvInputError, AcvModelError

# CRITICAL FIX: parents[2] points to the global Backend/model/ directory
# __file__ = Backend/ACV/core/model.py -> parents[2] = Backend/
MODEL_PATH = Path(__file__).resolve().parents[2] / "model" / "acv_model.json"


class AcvModel:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {
            "ambient_quantile": 0.5,
            "scoring_strategy": "borda_count"
        }
        quantile = self.config.get("ambient_quantile")
        if not isinstance(quantile, (int, float)) or not 0 <= quantile <= 1:
            raise AcvModelError("ACV model ambient_quantile must be between 0 and 1.")
        if self.config.get("scoring_strategy") != "borda_count":
            raise AcvModelError("ACV model scoring_strategy must be 'borda_count'.")

    @classmethod
    def load(cls, path: Path | str = MODEL_PATH) -> 'AcvModel':
        p = Path(path)
        if not p.exists():
            # Raise the exception so the FastAPI runner correctly catches it
            raise AcvModelError(f"Model file not found: {p}")
        try:
            with open(p, "r", encoding="utf-8") as f:
                return cls(json.load(f))
        except Exception as e:
            raise AcvModelError(f"Failed to load ACV model config: {e}")

    def save(self, path: Path | str = MODEL_PATH) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def predict(self, features: dict[str, pd.Series]) -> tuple[list[str], dict[str, float], bool]:
        """Combines shortfall and delivered cooling rankings via Borda count."""
        s1 = features["shortfall_scores"]
        s2 = features["delivered_scores"]

        if s1.empty or s2.empty:
            raise AcvInputError("The ACV export has no usable cooling observations.")
        if set(s1.index) != set(s2.index):
            raise AcvInputError("The ACV export has incomplete metrics for one or more cars.")

        score_table = pd.concat([s1.rename("shortfall"), s2.rename("delivered")], axis=1)
        if score_table.isna().any(axis=None):
            raise AcvInputError("The ACV export has incomplete metrics for one or more cars.")

        cars = sorted(set(s1.index) | set(s2.index))
        n = len(cars)

        def to_borda(scores: pd.Series) -> dict[str, int]:
            ranked = scores.reindex(cars).sort_values(ascending=False)
            return {car: n - i for i, car in enumerate(ranked.index)}

        p1 = to_borda(s1)
        p2 = to_borda(s2)
        total = {car: p1.get(car, 0) + p2.get(car, 0) for car in cars}

        ranked_cars = sorted(total, key=lambda c: total[c], reverse=True)
        agrees = bool(s1.idxmax() == s2.idxmax()) if not s1.empty and not s2.empty else True

        max_possible = 2 * n
        normalized_scores = {car: round(float(total[car] / max_possible), 3) for car in ranked_cars}

        return ranked_cars, normalized_scores, agrees
