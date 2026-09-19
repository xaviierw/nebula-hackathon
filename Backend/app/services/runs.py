"""Per-user run history.

Stored as a SUBCOLLECTION under each user -- users/{uid}/runs/{run_id} --
rather than a top-level collection with a uid field. That makes listing one
user's history a plain ordered query with no composite index, and makes
cross-user leakage structurally impossible rather than a code-review item.
"""

from __future__ import annotations

import logging

from google.cloud import firestore

log = logging.getLogger(__name__)


def _runs(db, uid: str):
    return db.collection("users").document(uid).collection("runs")


def record(db, uid: str, **fields) -> str | None:
    """Append a run. Returns its id, or None if the write failed.

    Called for failures as well as successes (status="error"), so a user can
    see that a file was rejected and why.
    """
    try:
        ref = _runs(db, uid).document()
        ref.set({**fields, "run_id": ref.id, "created_at": firestore.SERVER_TIMESTAMP})
        return ref.id
    except Exception:
        log.exception("Failed to record run for %s", uid)
        return None


def list_runs(db, uid: str, limit: int = 50, cursor: str | None = None):
    """Newest first, cursor-paginated. Returns (runs, next_cursor)."""
    query = _runs(db, uid).order_by("created_at", direction=firestore.Query.DESCENDING)
    if cursor:
        anchor = _runs(db, uid).document(cursor).get()
        if anchor.exists:
            query = query.start_after(anchor)
    docs = list(query.limit(limit).stream())
    runs = [d.to_dict() for d in docs]
    next_cursor = docs[-1].id if len(docs) == limit else None
    return runs, next_cursor


def get_run(db, uid: str, run_id: str) -> dict | None:
    """One run, scoped to this user by path construction."""
    snap = _runs(db, uid).document(run_id).get()
    return snap.to_dict() if snap.exists else None
