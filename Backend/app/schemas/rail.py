"""Rail Corrugation response contract.

Submission schema (Backend/01_Problem_Statement_3_Specifications.md section 4.1):
    rail_predictions.csv -> file_id,prediction
    prediction is one of: Normal, Side I, Side II
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Warning_

RailLabel = Literal["Normal", "Side I", "Side II"]


class VibrationMeasurements(BaseModel):
    rms_median: float
    rms_max: float
    abs_peak_max: float


class RailEvidence(BaseModel):
    samples_per_sensor: int
    column_count: int
    duration_seconds: float
    vibration_sensors_per_side: int
    feature_count: int
    side_i: VibrationMeasurements
    side_ii: VibrationMeasurements


class RailResult(BaseModel):
    prediction: RailLabel
    evidence: RailEvidence
    # Reserved for a calibrated future model; the current UI does not present
    # Extra Trees vote fractions as confidence.
    confidence: dict[str, float] = Field(default_factory=dict)
    warnings: list[Warning_] = Field(default_factory=list)
