"""Feature extraction for SHM.

Signal: Dynamic stress time series.

Keep this pure and deterministic -- the same file must always produce the same
features, because the API caches results by file hash and will not re-run the
model on a file it has already seen.
"""

from __future__ import annotations

import pandas as pd

# Column order the model was trained on. Training and prediction must agree,
# so define it once here and import it in both.
FEATURE_COLUMNS: list[str] = []


def extract(frame: pd.DataFrame) -> dict:
    """One file -> one feature dict."""
    raise NotImplementedError("SHM feature extraction not written yet")


def build_table(frames: dict) -> pd.DataFrame:
    """Many files -> a feature table, one row per file."""
    raise NotImplementedError("SHM feature table not written yet")
