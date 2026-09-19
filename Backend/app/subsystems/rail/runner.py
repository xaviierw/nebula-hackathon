"""Rail Corrugation runner -- NOT YET IMPLEMENTED.

To wire up Rail Corrugation:
  1. Build Backend/Rail_Corrugation/ (see its README.md) so that
     `prediction/predict.py` exposes a pure predict_file(frame, model, reference).
  2. Fill in the class below, copying Backend/app/subsystems/door/runner.py --
     it is the worked reference.
  3. In app/subsystems/registry.py replace
         register(NotImplementedRunner("rail-corrugation", "Rail Corrugation"))
     with
         register(RailRunner())

That is the entire API-side change. Do not add routes.

NOTE ON IMPORTS: Door occupies the top-level module names `core`, `training`
and `prediction` via its vendor_path shim. The second subsystem to be wired in
CANNOT reuse those names -- give Backend/Rail_Corrugation a package root, or
name its modules rail_core / rail_prediction. See Backend/README.md.
"""

from __future__ import annotations

# from ...schemas.rail import RailResult
# from ..base import SubsystemRunner
#
#
# class RailRunner(SubsystemRunner):
#     id = "rail-corrugation"
#     name = "Rail Corrugation"
#     upload_mode = "per-file"
#     response_model = RailResult
#
#     def load(self) -> None:
#         ...
#
#     def run(self, raw: bytes, filename: str) -> dict:
#         ...
