"""Dataset metadata -- facts ABOUT an uploaded file, never its contents.

This is what makes "this exact file has been analysed five times" answerable.
No bytes are stored here or anywhere else.
"""

from __future__ import annotations

import logging

from google.cloud import firestore

log = logging.getLogger(__name__)

COLLECTION = "datasets"
MAX_FILENAMES = 20


def touch(db, digest: str, *, size_bytes: int, filename: str, subsystem: str) -> None:
    """Record that a file with this hash was seen. Failures are non-fatal."""
    if db is None:  # DEV_NO_AUTH: no Firestore
        return
    try:
        ref = db.collection(COLLECTION).document(digest)
        snap = ref.get()
        payload = {
            "sha256": digest,
            "size_bytes": size_bytes,
            "seen_count": firestore.Increment(1),
            "subsystems": firestore.ArrayUnion([subsystem]),
            "last_seen_at": firestore.SERVER_TIMESTAMP,
        }
        # Cap the filename list so a file uploaded under many names cannot grow
        # the document without bound.
        existing = (snap.to_dict() or {}).get("filenames", []) if snap.exists else []
        if filename not in existing and len(existing) < MAX_FILENAMES:
            payload["filenames"] = firestore.ArrayUnion([filename])
        if not snap.exists:
            payload["first_seen_at"] = firestore.SERVER_TIMESTAMP
        ref.set(payload, merge=True)
    except Exception:
        log.exception("Failed to touch dataset %s", digest)
