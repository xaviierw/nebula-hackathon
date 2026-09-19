"""Rail Corrugation response contract -- PROVISIONAL, owned by its builder.

Submission schema (Backend/01_Problem_Statement_3_Specifications.md section 4.1):
    rail_predictions.csv -> file_id,prediction
    prediction is one of: Normal, Side I, Side II
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .common import Warning_

RailLabel = Literal["Normal", "Side I", "Side II"]


class RailResult(BaseModel):
    prediction: RailLabel
    # Per-class probability, for display. Optional.
    confidence: dict[str, float] = {}
    warnings: list[Warning_] = []
