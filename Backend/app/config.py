"""Settings, read once from Backend/.env.

Every value here is either non-secret configuration or a *path* to a secret --
never a secret itself. See Backend/README.md for the full variable list and
which ones matter.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Pinned, not configurable. Frontend/vite.config.ts proxies /api to port 8000
# and Frontend/src/api/client.ts hardcodes the /api prefix; making either of
# these an env var just invites someone to change one side and break the proxy.
API_PREFIX = "/api"
HOST = "127.0.0.1"
PORT = 8000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Firebase --------------------------------------------------------
    # The JSON file this points at IS the secret. Keep it outside the repo.
    firebase_credentials_file: Path | None = None
    firebase_project_id: str = ""

    # --- Access ----------------------------------------------------------
    # Comma-separated. Empty means any account Firebase accepts may sign in,
    # which for an internal tool with Google sign-on enabled means anyone with
    # a Google account. See the membership-gate note in Backend/README.md.
    allowed_email_domains: str = ""

    # --- Limits ----------------------------------------------------------
    max_upload_bytes: int = 26_214_400  # 25 MiB

    # --- Behaviour -------------------------------------------------------
    # Local-only escape hatch for frontend/model development. This disables
    # authentication and Firestore persistence, so it must never be enabled
    # in a shared or deployed environment.
    local_dev_mode: bool = False
    prediction_cache_enabled: bool = True
    log_level: str = "info"

    @property
    def allowed_domains(self) -> list[str]:
        return [d.strip().lower() for d in self.allowed_email_domains.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
