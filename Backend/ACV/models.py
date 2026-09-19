"""Bridge for the FastAPI runner to correctly load the ACV model."""

import sys
from pathlib import Path

# 1. Fix the import path so FastAPI can dynamically find your 'core' folder
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from core.model import AcvModel as OriginalAcvModel
from core.errors import AcvModelError

# 2. Wrap the class to force the correct absolute file path, ignoring FastAPI's relative paths
class AcvModel(OriginalAcvModel):
    @classmethod
    def load(cls, path=None):
        # Force the path to exactly where `python main.py train` saved it
        real_path = HERE / "model" / "acv_model.json"
        
        if not real_path.exists():
            raise AcvModelError("The ACV model has not been built yet.")
            
        return super().load(path=real_path)