"""Firebase Admin initialisation, and the two things the app needs from it.

Auth verification and Firestore both come from the one initialised app, so
there is exactly one credential and one project id in play.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials, firestore

from .config import Settings, get_settings

log = logging.getLogger(__name__)


def init_firebase(settings: Settings) -> None:
    """Initialise the Admin SDK. Raises if credentials are missing or bad.

    Deliberately fails loudly: every route on this API requires a verified
    token, so a server that cannot verify tokens is not partially useful.

    Uses an explicit service-account file rather than Application Default
    Credentials. With the gcloud SDK installed -- as it is on this machine --
    ADC would silently pick up a developer's personal gcloud login and appear
    to work, against whatever project that login defaults to.
    """
    if firebase_admin._apps:  # already initialised (uvicorn --reload re-imports)
        return

    path = settings.firebase_credentials_file
    if not path:
        raise RuntimeError(
            "FIREBASE_CREDENTIALS_FILE is not set.\n"
            "Copy Backend/.env.example to Backend/.env and point it at your "
            "service account JSON. See Backend/README.md."
        )
    if not path.exists():
        raise RuntimeError(
            f"Firebase service account file not found: {path}\n"
            "Download it from Firebase console -> Project settings -> Service "
            "accounts -> Generate new private key, and store it OUTSIDE this repo."
        )

    cred = credentials.Certificate(str(path))
    firebase_admin.initialize_app(cred)
    log.info("Firebase initialised (project=%s)", settings.firebase_project_id or "from key")


@lru_cache
def get_db():
    """The Firestore client, from the initialised Admin app."""
    if get_settings().local_dev_mode:
        return None
    return firestore.client()


def verify_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return its decoded claims.

    check_revoked is left False: it costs an Identity Platform round trip on
    every single request. Turn it on only if you also wire up token revocation
    and need it to bite immediately.
    """
    return auth.verify_id_token(id_token, check_revoked=False)
