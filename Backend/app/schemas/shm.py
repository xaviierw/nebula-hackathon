"""SHM response contract -- PROVISIONAL, owned by its builder.

Submission schema (Backend/01_Problem_Statement_3_Specifications.md section 4.1):
    shm_predictions.csv -> file_id,prediction
    prediction is a single numeric cumulative-damage value.
"""

from __future__ import annotations

from pydantic import BaseModel

from .common import Warning_


class ShmResult(BaseModel):
    # Cumulative fatigue damage. Regression, so this is a bare number.
    prediction: float
    # Optional [low, high] uncertainty band, for display.
    interval: list[float] | None = None
    warnings: list[Warning_] = []
