"""Build the deterministic ACV heuristic configuration artifact."""

from __future__ import annotations

from pathlib import Path
from core.model import AcvModel, MODEL_PATH


def main(argv=None) -> int:
    print(f"Writing ACV heuristic configuration to {MODEL_PATH}...")
    model = AcvModel(config={
        "ambient_quantile": 0.5,
        "scoring_strategy": "borda_count",
        "description": "Peer-relative shortfall + cooling delivered dual Borda ranking"
    })
    model.save(MODEL_PATH)
    print("Model configuration written successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
