"""The Door response contract.

FROZEN. Mirrors Frontend/src/features/door/types.ts field for field, which in
turn mirrors DoorClassifier.DETAIL_COLUMNS (Backend/Door/core/classifier.py:42).
Change one of the three and you must change all three.

Do NOT add an alias_generator to this module. These field names ARE the wire
format -- `steady_current_mA` under to_camel becomes `steadyCurrentMA` and the
frontend's results table renders empty cells. This is exactly the kind of thing
that looks like tidying up.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .common import Warning_


class DoorDetailRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Native Y-M-D-H-M-S-ms with zero-padding stripped, e.g. "2023-7-5-0-0-0-0".
    # NOT ISO-8601 and not Date-parseable -- produced by core/scoring.py
    # format_time(), and the frontend has its own formatTime.ts to read it.
    start_time: str
    end_time: str
    # Inclusive row indices into the uploaded CSV, so a caller can slice the
    # waveform for a cycle.
    start_row: int
    end_row: int
    operation: Literal["Open", "Close"]
    # Mean motor current across mid-travel (20%-85% of the leaf's own stroke).
    steady_current_mA: float
    threshold_mA: float
    prediction: Literal["Normal", "Abnormal resistance"]
    margin_ratio: float


class DoorWarning(Warning_):
    code: Literal["sampling_interval", "segment_duration"]


class DoorResult(BaseModel):
    detail: list[DoorDetailRow]
    warnings: list[DoorWarning]
