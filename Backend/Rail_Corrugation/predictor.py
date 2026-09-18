"""Standalone Rail Corrugation inference using the saved Extra Trees model.

predict_file(path) returns {"file_id": ..., "prediction": ...}.
predict_files(paths) returns a DataFrame with those two columns, in input order.
The default model is resolved relative to this file and is cached between calls.
Only pass trusted, application-controlled paths for model_path.
"""

from __future__ import annotations
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
import warnings
import joblib
import numpy as np
import pandas as pd
import scipy
from scipy import stats
import sklearn
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.exceptions import InconsistentVersionWarning, NotFittedError
from sklearn.utils.validation import check_is_fitted


DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "rail_corrugation.joblib"
CLASSES = ["Normal", "Side I", "Side II"]
SAMPLES_PER_FILE = 10_000
EPSILON = 1e-12
EXPECTED_HEADER = ["Rotating speed"] + [
    f"{kind} of bearing in position {position} of car {car}"
    for car in range(1, 9)
    for position in range(1, 9)
    for kind in ["Vibration", "Shock"]
]
SIDE_POSITIONS = {"side_i": [1, 3, 5, 7], "side_ii": [2, 4, 6, 8]}
VIBRATION_COLUMNS = {
    side: [
        f"Vibration of bearing in position {position} of car {car}"
        for car in range(1, 9)
        for position in positions
    ]
    for side, positions in SIDE_POSITIONS.items()
}
TIME_METRICS = [
    "rms_median", "rms_p90", "rms_max", "abs_peak_max",
    "kurtosis_median", "crest_factor_p90",
]
RATIO_METRICS = ["rms_p90", "rms_max", "abs_peak_max"]
FEATURE_COLUMNS = [
    f"vibration__{side}__{metric}"
    for side in SIDE_POSITIONS
    for metric in TIME_METRICS
] + [f"vibration__side_log_ratio__{metric}" for metric in RATIO_METRICS]

# This describes the notebook recipe stored in the existing model bundle.
# Inference computes only its 15 selected features; the unused spectral and
# speed settings remain here so a different training recipe is not accepted.
FEATURE_CONTRACT = {
    "recipe_version": "rail_features_v1",
    "samples_per_file": SAMPLES_PER_FILE,
    "sampling_rate_hz": 10_000,
    "ordered_columns": EXPECTED_HEADER,
    "input_dtype": "float32",
    "side_i_positions": SIDE_POSITIONS["side_i"],
    "side_ii_positions": SIDE_POSITIONS["side_ii"],
    "epsilon": EPSILON,
    "undefined_summary_value": 0.0,
    "welch_nperseg": 2048,
    "frequency_bands_hz": [(0, 50), (50, 100), (100, 250), (250, 1_000), (1_000, 5_000)],
    "wheel_diameter_m": 0.85,
    "speed_sensor_teeth": 90,
    "scaling": "none",
}


def _recording_path(file_path: str | Path) -> Path:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Sensor file not found: {path}")
    if path.suffix.lower() != ".csv":
        raise ValueError(f"{path.name}: expected a sensor recording in CSV format.")
    return path


def read_recording(file_path: str | Path) -> pd.DataFrame:
    """Read one numeric CSV with the exact 10,000-row, 129-column sensor schema."""
    path = _recording_path(file_path)
    try:
        # One extra row detects oversized recordings without reading the whole file.
        # Treat dropped-column warnings as errors, including an extra value in row 1.
        with warnings.catch_warnings():
            warnings.simplefilter("error", pd.errors.ParserWarning)
            frame = pd.read_csv(
                path, dtype=np.float32, nrows=SAMPLES_PER_FILE + 1,
                index_col=False, encoding="utf-8-sig",
            )
    except (ValueError, pd.errors.ParserWarning, UnicodeError) as exc:
        raise ValueError(
            f"{path.name}: invalid CSV; expected a header and numeric sensor measurements."
        ) from exc
    if frame.shape != (SAMPLES_PER_FILE, len(EXPECTED_HEADER)):
        raise ValueError(f"{path.name}: expected 10,000 rows and 129 sensor columns; got {frame.shape}.")
    if frame.columns.tolist() != EXPECTED_HEADER:
        raise ValueError(f"{path.name}: sensor column names or order do not match the Info Kit.")
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError(f"{path.name}: missing or non-finite sensor measurements.")
    return frame


def _finite_number(value: float) -> float:
    # Constant signals can give undefined kurtosis. Keep the notebook's fallback
    # for computed summaries; missing raw measurements have already been rejected.
    return float(value) if np.isfinite(value) else 0.0


def _time_summary(values: np.ndarray) -> dict[str, float]:
    """Summarise the 32 vibration sensors on one rail side, exactly as in training."""
    # First calculate across time (axis=0), then summarise across sensors.
    # Preserve float32 squaring and float64 accumulation to match the notebook.
    rms = np.sqrt(np.mean(np.square(values), axis=0, dtype=np.float64))
    peak = np.max(np.abs(values), axis=0)
    kurtosis = stats.kurtosis(values, axis=0, fisher=True, bias=False)
    crest = peak / (rms + EPSILON)
    return {
        "rms_median": _finite_number(np.median(rms)),
        "rms_p90": _finite_number(np.quantile(rms, 0.90)),
        "rms_max": _finite_number(np.max(rms)),
        "abs_peak_max": _finite_number(np.max(peak)),
        "kurtosis_median": _finite_number(np.median(kurtosis)),
        "crest_factor_p90": _finite_number(np.quantile(crest, 0.90)),
    }


def extract_features(file_path: str | Path) -> dict[str, float]:
    """Return only the 15 features selected by the final model, in training order."""
    frame = read_recording(file_path)
    features = {}
    for side, columns in VIBRATION_COLUMNS.items():
        values = frame[columns].to_numpy(dtype=np.float32, copy=False)
        features.update({
            f"vibration__{side}__{name}": value
            for name, value in _time_summary(values).items()
        })
    for metric in RATIO_METRICS:
        left = features[f"vibration__side_i__{metric}"]
        right = features[f"vibration__side_ii__{metric}"]
        # Positive = stronger Side I; negative = stronger Side II; zero = equal.
        features[f"vibration__side_log_ratio__{metric}"] = _finite_number(
            np.log((left + EPSILON) / (right + EPSILON))
        )
    if not np.isfinite(list(features.values())).all():
        raise ValueError(f"{Path(file_path).name}: invalid computed features.")
    return features


def _validate_bundle(bundle: object) -> dict:
    """Check that a saved model expects this exact feature recipe and environment."""
    if not isinstance(bundle, dict) or bundle.get("format_version") != 1:
        raise ValueError("Not a supported Rail Corrugation model bundle.")
    if bundle.get("feature_contract") != FEATURE_CONTRACT:
        raise ValueError("The saved model uses a different feature recipe.")
    if bundle.get("feature_columns") != FEATURE_COLUMNS:
        raise ValueError("The saved model has an unexpected feature order.")
    if bundle.get("classes") != CLASSES:
        raise ValueError("The saved model has unexpected classes.")

    model = bundle.get("model")
    if not isinstance(model, ExtraTreesClassifier):
        raise ValueError("The bundle must contain a fitted Extra Trees model.")
    try:
        check_is_fitted(model, ["estimators_", "feature_names_in_", "classes_", "n_features_in_"])
    except NotFittedError as exc:
        raise ValueError("The bundle's Extra Trees model is not fitted.") from exc
    if (list(model.feature_names_in_) != FEATURE_COLUMNS
            or list(model.classes_) != CLASSES
            or model.n_features_in_ != len(FEATURE_COLUMNS)):
        raise ValueError("The fitted model's features or classes do not match its metadata.")

    versions = bundle.get("versions", {})
    if not isinstance(versions, dict):
        raise ValueError("The saved model is missing its package versions.")
    current = {
        "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__,
        "sklearn": sklearn.__version__, "joblib": joblib.__version__,
    }
    mismatches = [
        f"{name}: model needs {versions.get(name)}, installed {version}"
        for name, version in current.items() if versions.get(name) != version
    ]
    if mismatches:
        raise ValueError("Model dependency mismatch; use requirements.txt. " + "; ".join(mismatches))
    return bundle


@lru_cache(maxsize=4)
def _cached_model(path: str, modified_ns: int, size: int) -> dict:
    # The file timestamp and size are cache keys: replacing the saved model reloads it.
    # joblib can execute pickle code; the model path must be application-controlled.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", InconsistentVersionWarning)
            bundle = joblib.load(path)
    except InconsistentVersionWarning as exc:
        raise ValueError(
            f"Model requires scikit-learn {exc.original_sklearn_version}; "
            f"installed {exc.current_sklearn_version}. Use requirements.txt."
        ) from exc
    except Exception as exc:
        raise ValueError(f"Could not load the saved model: {path}") from exc
    return _validate_bundle(bundle)


def load_rail_model(model_path: str | Path = DEFAULT_MODEL_PATH) -> dict:
    """Load and cache a trusted model bundle; usable once at application startup."""
    path = Path(model_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Saved model not found: {path}")
    info = path.stat()
    return _cached_model(str(path), info.st_mtime_ns, info.st_size)


def predict_files(
    file_paths: Iterable[str | Path], model_path: str | Path = DEFAULT_MODEL_PATH,
) -> pd.DataFrame:
    """Predict an ordered sequence of files; return file_id,prediction columns.

    Input order and source filenames are preserved. Empty input returns an empty
    table. Duplicate filenames or any invalid recording reject the whole batch.
    The returned table can be exported with .to_csv(output_path, index=False).
    """
    if isinstance(file_paths, (str, Path)):
        raise TypeError("Pass a sequence of paths, for example [path1, path2].")
    paths = [_recording_path(path) for path in file_paths]
    names = [path.name for path in paths]
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("Batch filenames must be unique so each file_id identifies one recording.")
    if not paths:
        return pd.DataFrame(columns=["file_id", "prediction"])
    bundle = load_rail_model(model_path)
    # Each raw file is processed separately; only its 15-feature summary is kept.
    rows = [extract_features(path) for path in paths]
    measurements = pd.DataFrame(rows).loc[:, bundle["feature_columns"]]
    predictions = bundle["model"].predict(measurements)
    return pd.DataFrame({"file_id": names, "prediction": predictions})


def predict_file(
    file_path: str | Path, model_path: str | Path = DEFAULT_MODEL_PATH,
) -> dict[str, str]:
    """Return one recording's filename and Normal, Side I, or Side II prediction."""
    return predict_files([file_path], model_path).iloc[0].to_dict()
