"""Shapes shared across subsystems."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    """The one error envelope. Declared so /api/docs advertises it correctly
    instead of FastAPI's default {"detail": ...}."""

    message: str


class Warning_(BaseModel):
    """A non-blocking caveat attached to a prediction.

    extra="allow" is load-bearing. Door's warn() helper
    (Backend/Door/prediction/predict.py:43) attaches arbitrary keys per warning
    -- operation, n_segments, expected_min, observed, start_times -- and
    Frontend/src/features/door/types.ts accepts them through an open index
    signature. Pydantic's default would silently strip every one of them, and
    you would not notice today because door_reference.json is missing so
    warnings is always []. It would surface after a retrain, looking like a
    model regression rather than a schema bug.
    """

    model_config = ConfigDict(extra="allow")

    code: str
    severity: Literal["warning", "info"]
    message: str


class SubsystemInfo(BaseModel):
    id: str
    name: str
    available: bool
    reason: str | None = None
    model_version: str
    upload_mode: Literal["stream", "per-file"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    firebase: bool
    subsystems: list[SubsystemInfo]


class RunSummary(BaseModel):
    run_id: str
    subsystem: str
    filename: str
    size_bytes: int
    file_sha256: str
    model_version: str
    created_at: datetime | None
    status: Literal["ok", "error"]
    cache_hit: bool
    error_message: str | None = None


class RunPage(BaseModel):
    runs: list[RunSummary]
    next_cursor: str | None = None


class BatchItem(BaseModel):
    filename: str
    ok: bool
    result: dict | None = None
    message: str | None = None


class BatchResponse(BaseModel):
    results: list[BatchItem]
