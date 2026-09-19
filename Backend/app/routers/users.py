"""The caller's own profile and history.

Every route here is scoped to the authenticated user by path construction --
there is no user id parameter to forget to check.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from ..deps import CurrentUserDep, DbDep
from ..errors import ApiError, NotFoundError
from ..schemas.common import ErrorResponse, RunPage, RunSummary
from ..schemas.user import UserOut, UserUpdate
from ..services import cache, runs, users

router = APIRouter(responses={401: {"model": ErrorResponse}})


@router.get("/me", response_model=UserOut)
def me(user: CurrentUserDep, db: DbDep):
    # Upserts as a safety net for a client that skipped /auth/session.
    return _as_out(users.upsert(db, user), user)


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: CurrentUserDep, db: DbDep):
    return _as_out(users.set_display_name(db, user.uid, body.display_name), user)


@router.get("/me/runs", response_model=RunPage)
def my_runs(
    user: CurrentUserDep,
    db: DbDep,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
):
    """This user's upload history, newest first."""
    rows, next_cursor = runs.list_runs(db, user.uid, limit=limit, cursor=cursor)
    return RunPage(
        runs=[RunSummary(**_summary(r)) for r in rows], next_cursor=next_cursor
    )


@router.get("/me/runs/{run_id}", responses={404: {"model": ErrorResponse}})
def my_run(run_id: str, user: CurrentUserDep, db: DbDep):
    """Re-view a past prediction, rehydrated from the shared cache.

    This is why results are cached rather than recomputed: history stays
    viewable without re-running a model.
    """
    run = runs.get_run(db, user.uid, run_id)
    if run is None:
        raise NotFoundError("That result could not be found.")

    if run.get("status") == "error":
        return {"run": _summary(run), "result": None}

    payload = cache.get(db, run.get("cache_key", ""))
    if payload is None:
        # The cache entry is gone -- almost always because the model was
        # retrained, which changes model_version and therefore the key.
        raise ApiError(
            "This result is no longer stored. The model has been updated "
            "since it was produced -- upload the file again to get a fresh "
            "result.",
            410,
        )
    return {"run": _summary(run), "result": payload}


def _summary(run: dict) -> dict:
    return {
        "run_id": run.get("run_id", ""),
        "subsystem": run.get("subsystem", ""),
        "filename": run.get("filename", ""),
        "size_bytes": run.get("size_bytes", 0),
        "file_sha256": run.get("file_sha256", ""),
        "model_version": run.get("model_version", ""),
        "created_at": run.get("created_at"),
        "status": run.get("status", "ok"),
        "cache_hit": bool(run.get("cache_hit", False)),
        "error_message": run.get("error_message"),
    }


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
