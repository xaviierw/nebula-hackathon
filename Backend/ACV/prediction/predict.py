"""ACV inference -- THIS FILE IS THE API SEAM."""

from __future__ import annotations

import pandas as pd

try:
    from ..core.errors import AcvInputError
    from ..core.data import check_schema, standardize_column_names, sanitize_sensor_data
    from ..core.features import calculate_train_ambient_ref, extract_features
    from ..core.model import AcvModel
except ImportError:
    # Keep the standalone `python main.py predict` entry point working.
    from core.errors import AcvInputError
    from core.data import check_schema, standardize_column_names, sanitize_sensor_data
    from core.features import calculate_train_ambient_ref, extract_features
    from core.model import AcvModel


def warn(code: str, severity: str, message: str, **extra) -> dict:
    """Build a structured, non-blocking caveat."""
    return {"code": code, "severity": severity, "message": message, **extra}


def predict_file(frame: pd.DataFrame, model: AcvModel | None = None, reference: dict | None = None) -> dict:
    """Score one ACV file.

    Returns:
        {"ranked_cars": ["01", "03", ...], "scores": {"01": 0.94, ...}, "warnings": []}
    """
    check_schema(frame)

    if model is None:
        model = AcvModel.load()

    df = standardize_column_names(frame.copy())
    df = sanitize_sensor_data(df)
    df = calculate_train_ambient_ref(df)

    quantile = model.config.get("ambient_quantile", 0.5)
    features = extract_features(df, ambient_quantile=quantile)

    ranked_cars, scores, agrees = model.predict(features)

    warnings = []
    if not agrees:
        warnings.append(
            warn(
                code="DISAGREEING_FEATURES",
                severity="warning",
                message="Primary shortfall and cooling delivered metrics disagree on the most faulty car."
            )
        )

    # Return pure Python types for Pydantic/FastAPI
    return {
        "ranked_cars": [str(c) for c in ranked_cars],
        "scores": {str(k): float(v) for k, v in scores.items()},
        "warnings": warnings,
    }