"""The error envelope, and the handlers that enforce it.

Every error response this API produces is `{"message": "..."}` -- never
FastAPI's default `{"detail": ...}`. That is not a style choice: the Door
success body already has a top-level `detail` field (the per-cycle rows), so
`Frontend/src/features/door/runPrediction.ts` reads `problem.message` and a
`detail` key on an error would collide with the success shape.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class ApiError(Exception):
    """Base for errors this API raises deliberately."""

    status_code = 500

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(ApiError):
    status_code = 404


class PayloadTooLargeError(ApiError):
    status_code = 413


class SubsystemNotImplementedError(ApiError):
    """Nobody has built this model yet."""

    status_code = 501

    def __init__(self, name: str) -> None:
        super().__init__(f"The {name} model has not been built yet.")


class SubsystemUnavailableError(ApiError):
    """The model exists, but is not usable on this machine right now.

    Kept distinct from 501 on purpose: 501 means "no one wrote it", 503 means
    "it exists and something here is missing" -- usually a model artifact.
    """

    status_code = 503


def is_domain_error(exc: BaseException) -> bool:
    """True for a subsystem's own <X>InputError / <X>ModelError.

    Matched by name rather than by import so this module never has to know
    which subsystems exist, or drag their packages onto sys.path.
    """
    return any(
        base.__name__.endswith(("InputError", "ModelError"))
        for base in type(exc).__mro__
    )


def _json(status: int, message: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse({"message": message}, status_code=status, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return _json(exc.status_code, exc.message)

    # Registered against STARLETTE's HTTPException, not FastAPI's. FastAPI's
    # subclasses Starlette's and its default handler is bound to the Starlette
    # class -- binding only to the FastAPI one would leave router-generated
    # 404s and 405s returning {"detail": "Not Found"}, which is precisely the
    # collision this module exists to prevent.
    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        # exc.headers carries WWW-Authenticate on 401s; dropping it would make
        # the response non-compliant.
        return _json(exc.status_code, str(exc.detail), getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        errors = exc.errors()
        message = _flatten(errors)
        # The second key is "fields", never "detail" -- see module docstring.
        return JSONResponse(
            {"message": message, "fields": _safe(errors)}, status_code=422
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        # A subsystem's own error reaches here rather than through an
        # @exception_handler of its own: those classes live outside this
        # package (Backend/Door/core/errors.py and its siblings) and are only
        # importable once that subsystem is on sys.path, so this module cannot
        # name them. Starlette dispatches handlers by class, so the catch-all
        # is the one place that can see them.
        #
        # <X>InputError messages are written for a non-technical reader and
        # are contractually safe to show verbatim -- that is the whole point
        # of the type. <X>ModelError means a missing or broken artifact: real
        # but not the user's fault, hence 503 rather than 400.
        if is_domain_error(exc):
            status = 503 if type(exc).__name__.endswith("ModelError") else 400
            log.info("%s: %s", type(exc).__name__, exc)
            return _json(status, str(exc))

        # Never echo an arbitrary exception string: that is how file paths and
        # stack internals leak into a user-facing message.
        log.exception("Unhandled error", exc_info=exc)
        return _json(500, "Something went wrong on our side. Please try again.")


def _flatten(errors: list[dict]) -> str:
    """Turn pydantic's error list into one sentence a person can act on."""
    if not errors:
        return "That request could not be processed."
    first = errors[0]
    loc = [str(p) for p in first.get("loc", []) if p not in ("body", "query", "path")]
    field = ".".join(loc)
    if field == "file" and first.get("type") == "missing":
        return "Attach the data file in a form field named 'file'."
    msg = first.get("msg", "is not valid")
    return f"{field or 'Request'}: {msg}"


def _safe(errors: list[dict]) -> list[dict]:
    """Drop the `ctx` key, which can hold non-serialisable exception objects."""
    return [{k: v for k, v in e.items() if k != "ctx"} for e in errors]
