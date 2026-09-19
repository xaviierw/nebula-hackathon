"""User profile storage.

One kind of user: there is no role, tier or permission field here by design.
Everyone who authenticates has identical access.
"""

from __future__ import annotations

import logging

from google.cloud import firestore

from ..deps import CurrentUser

log = logging.getLogger(__name__)

COLLECTION = "users"


def upsert(db, user: CurrentUser) -> dict:
    """Create or refresh the caller's profile document.

    The document id IS the Firebase uid, so there is no lookup table and no id
    mapping to keep in sync.

    Called from /api/auth/session after sign-in rather than from the auth
    dependency: putting it in the dependency would mean a Firestore write on
    every single request.
    """
    ref = db.collection(COLLECTION).document(user.uid)
    snap = ref.get()

    payload = {
        "uid": user.uid,
        "email": user.email,
        "photo_url": user.picture,
        "last_seen_at": firestore.SERVER_TIMESTAMP,
        "sign_in_count": firestore.Increment(1),
    }
    if not snap.exists:
        payload["created_at"] = firestore.SERVER_TIMESTAMP
        payload["display_name"] = user.name or (user.email or "").split("@")[0]

    ref.set(payload, merge=True)
    return ref.get().to_dict() or {}


def get(db, uid: str) -> dict | None:
    snap = db.collection(COLLECTION).document(uid).get()
    return snap.to_dict() if snap.exists else None


def set_display_name(db, uid: str, name: str) -> dict:
    ref = db.collection(COLLECTION).document(uid)
    ref.set({"display_name": name}, merge=True)
    return ref.get().to_dict() or {}
