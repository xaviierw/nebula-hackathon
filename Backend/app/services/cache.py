"""The shared prediction cache.

Keyed on (subsystem, model_version, file hash) with no user id, so if any
employee has already analysed a file, nobody re-runs the model on it. The
models are deterministic, so this is safe.

Because model_version is part of the key, retraining invalidates every entry
by itself -- there is no purge step and old results stay readable for history.
"""

from __future__ import annotations

import json
import logging

from google.cloud import firestore

COLLECTION = "predictions"

# Firestore's hard document limit is ~1 MiB. Stay well under it and skip the
# write rather than failing a request that already produced a good result.
MAX_PAYLOAD_BYTES = 700_000

log = logging.getLogger(__name__)


def cache_key(subsystem: str, model_version: str, digest: str) -> str:
    # Document ids may not contain "/", so join with "__". Keeps the key
    # readable in the Firestore console, which matters when debugging.
    return f"{subsystem}__{model_version}__{digest}"


def get(db, key: str) -> dict | None:
    """Return a cached payload, or None. Never raises on a cache miss."""
    if db is None:  # DEV_NO_AUTH: no Firestore, so every lookup is a miss
        return None
    try:
        snap = db.collection(COLLECTION).document(key).get()
    except Exception:
        log.exception("Cache read failed for %s", key)
        return None
    if not snap.exists:
        return None
    raw = snap.to_dict().get("payload_json")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Corrupt cache payload at %s; treating as a miss", key)
        return None


def put(
    db,
    key: str,
    *,
    subsystem: str,
    model_version: str,
    digest: str,
    payload: dict,
    uid: str,
    duration_ms: int,
) -> None:
    """Store a result. Failures are logged, never raised.

    A prediction that succeeded must not turn into a 500 because the cache
    write failed.

    NOTE: never cache failures. An input error is deterministic and it is
    tempting, but a transient error written into a shared cache becomes
    permanent for everyone.
    """
    if db is None:  # DEV_NO_AUTH: nothing to write to
        return

    body = json.dumps(payload, separators=(",", ":"))
    if len(body) > MAX_PAYLOAD_BYTES:
        log.warning(
            "Result for %s is %d bytes, over the %d cache limit; not caching",
            key, len(body), MAX_PAYLOAD_BYTES,
        )
        return

    try:
        db.collection(COLLECTION).document(key).set(
            {
                "subsystem": subsystem,
                "model_version": model_version,
                "file_sha256": digest,
                # Stored as a JSON string, not a nested map: exact round-trip,
                # no index bloat from thousands of rows, and it sidesteps
                # Firestore's "arrays cannot contain arrays" rule that
                # warnings[].observed sails close to.
                #
                # REQUIRES a single-field index exemption on payload_json --
                # see Backend/README.md. Without it, large writes are rejected
                # by the 1500-byte index entry limit.
                "payload_json": body,
                "payload_bytes": len(body),
                "n_rows": _row_count(payload),
                "duration_ms": duration_ms,
                # Debugging only. MUST NOT be returned to a client -- it is the
                # one cross-user identity leak in this design.
                "first_run_by": uid,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )
    except Exception:
        log.exception("Cache write failed for %s", key)


def _row_count(payload: dict) -> int | None:
    rows = payload.get("detail")
    return len(rows) if isinstance(rows, list) else None
