"""The one prediction path, shared by all four subsystems.

Routers are generated from the registry rather than hand-written per
subsystem, so a new model inherits auth, caching, history and error mapping
without touching this file.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, File, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..deps import CurrentUserDep, DbDep
from ..errors import (
    ApiError,
    PayloadTooLargeError,
    SubsystemNotImplementedError,
    SubsystemUnavailableError,
)
from ..schemas.common import BatchItem, BatchResponse, ErrorResponse
from ..services import cache, datasets, runs
from ..services.hashing import sha256_hex
from ..subsystems.registry import get_runner

log = logging.getLogger(__name__)

_ERRORS = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    501: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def build_subsystem_router(subsystem_id: str) -> APIRouter:
    runner = get_runner(subsystem_id)
    router = APIRouter()

    @router.post(
        "/predict",
        response_model=runner.response_model,
        responses=_ERRORS,
        summary=f"Run the {runner.name} model on one file",
    )
    async def predict(
        request: Request,
        response: Response,
        user: CurrentUserDep,
        db: DbDep,
        file: UploadFile = File(...),
    ):
        payload, meta = await _predict_one(request, user, db, file, subsystem_id)
        # Cache status travels as a header, not a body field: the Door success
        # body is frozen by the frontend contract and cannot grow keys.
        response.headers["X-Prediction-Cache"] = "hit" if meta["cache_hit"] else "miss"
        if meta["run_id"]:
            response.headers["X-Run-Id"] = meta["run_id"]
        return payload

    @router.post(
        "/predict-batch",
        response_model=BatchResponse,
        responses=_ERRORS,
        summary=f"Run the {runner.name} model on several files",
    )
    async def predict_batch(
        request: Request,
        user: CurrentUserDep,
        db: DbDep,
        files: list[UploadFile] = File(...),
    ):
        """For the one-row-per-file subsystems (ACV, Rail, SHM), which need
        many files to build a submission CSV.

        Per-file errors are reported inline rather than failing the whole
        batch -- one bad file in thirty should not discard the other results.
        """
        items: list[BatchItem] = []
        for f in files:
            try:
                payload, _ = await _predict_one(
                    request, user, db, f, subsystem_id, check_declared_size=False
                )
                items.append(BatchItem(filename=f.filename or "", ok=True, result=payload))
            except ApiError as exc:
                items.append(
                    BatchItem(filename=f.filename or "", ok=False, message=exc.message)
                )
            except Exception as exc:
                if _is_domain_error(exc):
                    items.append(
                        BatchItem(filename=f.filename or "", ok=False, message=str(exc))
                    )
                else:
                    raise
        return BatchResponse(results=items)

    return router


async def _predict_one(
    request,
    user,
    db,
    file: UploadFile,
    subsystem_id: str,
    *,
    check_declared_size: bool = True,
):
    runner = get_runner(subsystem_id)
    settings = get_settings()

    # Gate on availability BEFORE reading a byte. 501 means nobody built this
    # model; 503 means it exists but is not installed here.
    if not runner.available:
        if runner.model_version == "unavailable" and _is_stub(runner):
            raise SubsystemNotImplementedError(runner.name)
        raise SubsystemUnavailableError(
            runner.unavailable_reason or f"{runner.name} is not available right now."
        )

    # Reject oversized uploads before buffering them.
    # Content-Length is the whole multipart body. It is a useful early reject
    # for the one-file endpoint, but on /predict-batch it is the sum of every
    # valid file and must not be compared with the per-file limit.
    declared = request.headers.get("content-length")
    if (
        check_declared_size
        and declared
        and declared.isdigit()
        and int(declared) > settings.max_upload_bytes
    ):
        raise PayloadTooLargeError(
            f"That file is too large. The limit is "
            f"{settings.max_upload_bytes // (1024 * 1024)} MB."
        )

    raw = await file.read()
    try:
        if not raw:
            raise ApiError("The uploaded file is empty.", 400)
        if len(raw) > settings.max_upload_bytes:
            raise PayloadTooLargeError(
                f"That file is too large. The limit is "
                f"{settings.max_upload_bytes // (1024 * 1024)} MB."
            )

        filename = file.filename or "upload"
        digest = sha256_hex(raw)
        key = cache.cache_key(runner.id, runner.model_version, digest)

        payload = (
            cache.get(db, key)
            if settings.prediction_cache_enabled
            else None
        )
        cache_hit = payload is not None
        duration_ms = 0

        if not cache_hit:
            started = time.perf_counter()
            try:
                # Off the event loop: the model is synchronous pandas work.
                payload = await run_in_threadpool(runner.run, raw, filename)
            except Exception as exc:
                if _is_domain_error(exc):
                    runs.record(
                        db, user.uid,
                        subsystem=runner.id, filename=filename, size_bytes=len(raw),
                        file_sha256=digest, model_version=runner.model_version,
                        cache_key=key, cache_hit=False, status="error",
                        error_message=str(exc),
                    )
                    status = 503 if any(base.__name__.endswith("ModelError") for base in type(exc).__mro__) else 400
                    raise ApiError(str(exc), status) from exc
                raise
            duration_ms = int((time.perf_counter() - started) * 1000)
            if settings.prediction_cache_enabled:
                cache.put(
                    db, key,
                    subsystem=runner.id, model_version=runner.model_version,
                    digest=digest, payload=payload, uid=user.uid,
                    duration_ms=duration_ms,
                )

        datasets.touch(
            db, digest, size_bytes=len(raw), filename=filename, subsystem=runner.id
        )
        run_id = runs.record(
            db, user.uid,
            subsystem=runner.id, filename=filename, size_bytes=len(raw),
            file_sha256=digest, model_version=runner.model_version,
            cache_key=key, cache_hit=cache_hit, status="ok",
            duration_ms=duration_ms, error_message=None,
        )
        return payload, {"cache_hit": cache_hit, "run_id": run_id}
    finally:
        # Requirement: uploaded bytes never outlive the request.
        del raw
        await file.close()


def _is_stub(runner) -> bool:
    from ..subsystems.stubs import NotImplementedRunner

    return isinstance(runner, NotImplementedRunner)


def _is_domain_error(exc: Exception) -> bool:
    """True for a subsystem's own <X>InputError / <X>ModelError.

    Matched by name rather than by import so this module never has to know
    which subsystems exist, or drag their packages onto sys.path.
    """
    return any(
        base.__name__.endswith(("InputError", "ModelError"))
        for base in type(exc).__mro__
    )
