"""ACV inference -- THIS FILE IS THE API SEAM.

`predict_file` below is what Backend/app/subsystems/acv/runner.py calls. Its
contract is fixed; everything else in this subsystem is yours to design.

  * PURE. No file IO, no printing, no sys.exit. It receives a parsed DataFrame
    and returns JSON-ready data.
  * Raise AcvInputError for anything the user could fix -- the message is
    shown to them verbatim.
  * Return plain int / float / str, never numpy scalars. np.int64 is not a
    subclass of int and Pydantic will reject it.

Reference implementation: Backend/Door/prediction/predict.py:167 predict_stream.
"""

from __future__ import annotations

import pandas as pd

from core.errors import AcvInputError  # noqa: F401  (raise this for bad input)


def warn(code: str, severity: str, message: str, **extra) -> dict:
    """Build a structured, non-blocking caveat.

    Extra keys are preserved all the way to the browser -- the API warning
    schema sets extra="allow" precisely so your supporting numbers survive.
    """
    return {"code": code, "severity": severity, "message": message, **extra}


def predict_file(frame: pd.DataFrame, model, reference: dict | None = None) -> dict:
    """Score one ACV file.

    Returns, for this subsystem:
        {"ranked_cars": ["03", "01", "02"], "scores": {"03": 0.91}, "warnings": []}

    See Backend/app/schemas/acv.py (AcvResult) for the response
    model, and adjust it if your output differs.
    """
    raise NotImplementedError("ACV prediction not written yet")
