"""FastAPI dependencies: who is calling, and the database handle."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as fb_auth

from .config import get_settings
from .errors import ApiError
from .firebase import get_db, verify_token

log = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)
_WWW = {"WWW-Authenticate": "Bearer"}


@dataclass(frozen=True)
class CurrentUser:
    uid: str
    email: str | None
    name: str | None
    picture: str | None
    email_verified: bool


class AuthError(ApiError):
    status_code = 401


DEV_USER = CurrentUser(
    uid="dev-local",
    email="dev@localhost",
    name="Local Dev",
    picture=None,
    email_verified=True,
)


def get_db_dep():
    """The Firestore handle, or None when DEV_NO_AUTH is on.

    None is a supported value here, not a degraded one: every database call on
    the prediction path is already best-effort and non-fatal, so skipping them
    costs the shared cache, the run history and the dataset counters, and
    nothing else. The model still runs and the result still comes back.
    """
    if get_settings().dev_no_auth:
        return None
    return get_db()


def get_current_user(
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    """Verify the bearer token and identify the caller.

    Declared `def`, not `async def`, on purpose. verify_id_token does blocking
    work -- and a network fetch of Google's public certs when its cache is
    cold. FastAPI runs sync dependencies in a threadpool; an async version
    would stall the event loop on every request.
    """
    # Checked before the credential, not after: with the bypass on there is no
    # Firebase app initialised at all, so verify_token could not run anyway.
    if get_settings().dev_no_auth:
        return DEV_USER

    if cred is None or not cred.credentials:
        raise AuthError("Sign in to continue.")

    try:
        claims = verify_token(cred.credentials)
    except fb_auth.ExpiredIdTokenError:
        # Distinguished from "invalid" so the frontend can refresh the token
        # with getIdToken(true) and retry once, instead of bouncing the user
        # to /login every hour.
        raise AuthError("Your session has expired. Please sign in again.") from None
    except fb_auth.RevokedIdTokenError:
        raise AuthError("Your session was signed out. Please sign in again.") from None
    except fb_auth.CertificateFetchError as exc:
        log.warning("Could not fetch Google signing certs: %s", exc)
        raise ApiError(
            "Could not reach the sign-in service. Try again in a moment.", 503
        ) from None
    except (fb_auth.InvalidIdTokenError, ValueError):
        raise AuthError("Your sign-in could not be verified. Please sign in again.") from None

    email = claims.get("email")
    _check_membership(email)

    return CurrentUser(
        uid=claims["uid"],
        email=email,
        name=claims.get("name"),
        picture=claims.get("picture"),
        email_verified=bool(claims.get("email_verified", False)),
    )


def _check_membership(email: str | None) -> None:
    """Gate on email domain, if one is configured.

    This is membership, not a role: every user who gets through has identical
    permissions. It exists because Firebase Auth with a public provider
    enabled will happily authenticate any account in the world, and this is an
    internal tool.
    """
    domains = get_settings().allowed_domains
    if not domains:
        return
    if not email or email.rsplit("@", 1)[-1].lower() not in domains:
        raise ApiError("This account is not permitted to use this system.", 403)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
DbDep = Annotated[object | None, Depends(get_db_dep)]
