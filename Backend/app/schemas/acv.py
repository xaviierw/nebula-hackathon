"""ACV response contract -- PROVISIONAL, owned by whoever builds ACV.

Submission schema (Backend/01_Problem_Statement_3_Specifications.md section 4.1):
    acv_predictions.csv -> file_id,ranked_cars

Note there is NO `prediction` column. `ranked_cars` lists every car in the file
from most- to least-likely faulty, using the car identifier exactly as it
appears in that file's own column headers (e.g. "03", not "Car 3"), joined with
a pipe. Adjust the extra fields below to whatever your model actually produces;
keep `ranked_cars` as the authoritative ordering.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import Warning_


class AcvResult(BaseModel):
    # Ordered most- to least-likely faulty. Joining with "|" produces the
    # ranked_cars submission cell.
    ranked_cars: list[str]
    # Optional per-car score, for display. Shape is yours to choose.
    scores: dict[str, float] = Field(default_factory=dict)
    warnings: list[Warning_] = Field(default_factory=list)
