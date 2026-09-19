"""Sign-in lifecycle.

Firebase does the actual authentication in the browser. This router exists so
the backend learns about a user the first time they appear, and so the
frontend has something to verify a token against.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from firebase_admin import auth as fb_auth

from ..deps import CurrentUserDep, DbDep
from ..schemas.common import ErrorResponse
from ..schemas.user import UserOut
from ..services import users

router = APIRouter(responses={401: {"model": ErrorResponse}})


@router.post("/session", response_model=UserOut)
def open_session(user: CurrentUserDep, db: DbDep):
    """Call once after Firebase sign-in resolves.

    Creates the user's Firestore document on first sign-in. This is the write
    that the auth dependency deliberately does NOT do, so that verifying a
    token on every request stays read-only.
    """
    return _as_out(users.upsert(db, user), user)


@router.get("/me", response_model=UserOut)
def whoami(user: CurrentUserDep, db: DbDep):
    """Verify the caller's token. Read-only."""
    return _as_out(users.get(db, user.uid) or {}, user)


@router.post("/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke(user: CurrentUserDep):
    """Invalidate every refresh token this user holds.

    There is no /logout endpoint on purpose: Firebase sign-out happens
    entirely in the browser, and a server endpoint that returns 204 and does
    nothing would be misleading. This is the real server-side sign-out -- but
    note it only bites if verification passes check_revoked=True, which costs
    a round trip per request. See app/firebase.py.
    """
    fb_auth.revoke_refresh_tokens(user.uid)


def _as_out(doc: dict, user: CurrentUserDep) -> dict:
    return {
        "uid": user.uid,
        "email": doc.get("email", user.email),
        "display_name": doc.get("display_name", user.name),
        "photo_url": doc.get("photo_url", user.picture),
        "created_at": doc.get("created_at"),
        "last_seen_at": doc.get("last_seen_at"),
        "sign_in_count": doc.get("sign_in_count", 0),
    }
