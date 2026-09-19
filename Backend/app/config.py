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
    prediction_cache_enabled: bool = True
    log_level: str = "info"

    # --- Local development ----------------------------------------------
    # Skip Firebase entirely: no service-account key, no Firestore, and every
    # request attributed to one fake user. It exists so the model path can be
    # exercised end to end before the Firebase project is set up, and so a
    # teammate without a key can still run the whole app.
    #
    # With this on there is NO authentication of any kind. main.py refuses to
    # start unless the server is bound to loopback, and logs a banner every
    # time, because the failure mode of shipping it by accident is total.
    dev_no_auth: bool = False

    @property
    def allowed_domains(self) -> list[str]:
        return [d.strip().lower() for d in self.allowed_email_domains.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
