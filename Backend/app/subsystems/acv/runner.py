"""ACV runner -- NOT YET IMPLEMENTED.

To wire up ACV:
  1. Build Backend/ACV/ (see its README.md) so that
     `prediction/predict.py` exposes a pure predict_file(frame, model, reference).
  2. Fill in the class below, copying Backend/app/subsystems/door/runner.py --
     it is the worked reference.
  3. In app/subsystems/registry.py replace
         register(NotImplementedRunner("acv", "ACV"))
     with
         register(AcvRunner())

That is the entire API-side change. Do not add routes.

NOTE ON IMPORTS: Door occupies the top-level module names `core`, `training`
and `prediction` via its vendor_path shim. The second subsystem to be wired in
CANNOT reuse those names -- give Backend/ACV a package root, or name its
modules acv_core / acv_prediction. See Backend/README.md.
"""

from __future__ import annotations

# from ...schemas.acv import AcvResult
# from ..base import SubsystemRunner
#
#
# class AcvRunner(SubsystemRunner):
#     id = "acv"
#     name = "ACV"
#     upload_mode = "per-file"
#     response_model = AcvResult
#
#     def load(self) -> None:
#         ...
#
#     def run(self, raw: bytes, filename: str) -> dict:
#         ...
