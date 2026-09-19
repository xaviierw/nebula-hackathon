"""Rail Corrugation inference seam used by the shared FastAPI runner.

The validated notebook-parity implementation remains consolidated in
``Rail_Corrugation.predictor``. Re-exporting the production entry points here
keeps the subsystem contract identical to Door/ACV/SHM without introducing
their top-level ``prediction`` import collision.
"""

from __future__ import annotations

from ..predictor import DEFAULT_MODEL_PATH, analyse_bytes, load_rail_model

__all__ = ["DEFAULT_MODEL_PATH", "analyse_bytes", "load_rail_model"]
