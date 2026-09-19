"""SHM content-only response; upload identifiers remain request metadata."""
from pydantic import BaseModel, Field

from .common import Warning_


class ShmResult(BaseModel):
    prediction: float = Field(gt=0, allow_inf_nan=False)
    observations: int = Field(gt=0)
    weighted_cycle_count: float = Field(gt=0, allow_inf_nan=False)
    model_id: str
    model_version: str
    interval: None = None  # No validated uncertainty interval is available.
    warnings: list[Warning_] = Field(default_factory=list)
