"""SHM runner -- NOT YET IMPLEMENTED.

To wire up SHM:
  1. Build Backend/SHM/ (see its README.md) so that
     `prediction/predict.py` exposes a pure predict_file(frame, model, reference).
  2. Fill in the class below, copying Backend/app/subsystems/door/runner.py --
     it is the worked reference.
  3. In app/subsystems/registry.py replace
         register(NotImplementedRunner("shm", "SHM"))
     with
         register(ShmRunner())

That is the entire API-side change. Do not add routes.

NOTE ON IMPORTS: Door occupies the top-level module names `core`, `training`
and `prediction` via its vendor_path shim. The second subsystem to be wired in
CANNOT reuse those names -- give Backend/SHM a package root, or name its
modules shm_core / shm_prediction. See Backend/README.md.
"""

from __future__ import annotations

# from ...schemas.shm import ShmResult
# from ..base import SubsystemRunner
#
#
# class ShmRunner(SubsystemRunner):
#     id = "shm"
#     name = "SHM"
#     upload_mode = "per-file"
#     response_model = ShmResult
#
#     def load(self) -> None:
#         ...
#
#     def run(self, raw: bytes, filename: str) -> dict:
#         ...
