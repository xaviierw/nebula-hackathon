"""Nebula condition-monitoring API.

Run from this directory:

    ..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

Must be 127.0.0.1:8000 and mounted under /api: Frontend/vite.config.ts proxies
/api there, which is also why there is no CORS middleware -- every request the
browser makes is same-origin.

See README.md in this directory for the full design.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.formparsers import MultiPartParser

from app.config import API_PREFIX, HOST, PORT, get_settings
from app.errors import install_error_handlers
from app.firebase import init_firebase
from app.routers import auth, users
from app.routers.subsystems import build_subsystem_router
from app.schemas.common import HealthResponse
from app.subsystems.registry import all_runners, load_all

log = logging.getLogger(__name__)


def _refuse_unless_loopback() -> None:
    """Hard-stop DEV_NO_AUTH on anything but a loopback bind.

    config.HOST is pinned to 127.0.0.1, but uvicorn is normally started from
    the command line, where --host overrides it. Reading argv is the only way
    this process can see the address it was actually given, so that is what
    gets checked. This is a backstop against one careless command, not a
    security boundary -- the real guarantee is that DEV_NO_AUTH never reaches
    a deployed environment.
    """
    argv = sys.argv
    host = None
    for i, arg in enumerate(argv):
        if arg == "--host" and i + 1 < len(argv):
            host = argv[i + 1]
        elif arg.startswith("--host="):
            host = arg.split("=", 1)[1]

    if host is not None and host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(
            f"DEV_NO_AUTH is set but this server was told to bind {host}.\n"
            "The bypass disables authentication completely and is refused on "
            "any non-loopback address. Unset DEV_NO_AUTH in Backend/.env, or "
            "bind 127.0.0.1."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if settings.dev_no_auth:
        _refuse_unless_loopback()
        log.warning(
            "\n"
            "  ==========================================================\n"
            "   DEV_NO_AUTH is ON. There is NO authentication.\n"
            "   Every request runs as the fake user 'dev-local', and\n"
            "   Firestore is disabled: no cache, no run history.\n"
            "   Local development only. Never deploy with this set.\n"
            "  =========================================================="
        )
    else:
        # Fails loudly and deliberately. Every route requires a verified
        # token, so a server that cannot verify tokens is not partially
        # useful.
        init_firebase(settings)

    # Degrades per subsystem: one model missing must never take down the rest.
    load_all()
    for runner in all_runners():
        state = "ready" if runner.available else f"unavailable ({runner.unavailable_reason})"
        log.info("subsystem %-16s %s", runner.id, state)

    yield


def create_app() -> FastAPI:
    settings = get_settings()

    # Starlette backs UploadFile with a SpooledTemporaryFile capped at 1 MiB;
    # above that it silently writes the upload to %TEMP%. Uploaded bytes must
    # never touch disk, so raise the ceiling above the size limit we enforce
    # and reject anything larger outright.
    MultiPartParser.spool_max_size = settings.max_upload_bytes + 1

    app = FastAPI(
        title="Nebula API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    install_error_handlers(app)

    app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["auth"])
    app.include_router(users.router, prefix=f"{API_PREFIX}/users", tags=["users"])

    # One router per subsystem, generated from the registry rather than
    # hand-written, so adding a model needs no change here.
    for runner in all_runners():
        app.include_router(
            build_subsystem_router(runner.id),
            prefix=f"{API_PREFIX}/{runner.id}",
            tags=[runner.id],
        )

    @app.get(f"{API_PREFIX}/subsystems", tags=["meta"])
    def subsystems():
        """What exists and what is usable. Drives the frontend's dashboard."""
        return [r.info() for r in all_runners()]

    @app.get(f"{API_PREFIX}/health", response_model=HealthResponse, tags=["meta"])
    def health():
        """Unauthenticated. The first thing to check when something is wrong."""
        import firebase_admin

        return {
            "status": "ok",
            "firebase": bool(firebase_admin._apps),
            "subsystems": [r.info() for r in all_runners()],
        }

    if settings.dev_no_auth:
        # Visible proof the bypass is on, so "why is it not asking me to sign
        # in" is answerable without reading the server log.
        @app.get(f"{API_PREFIX}/dev-status", tags=["meta"])
        def dev_status():
            return {"dev_no_auth": True, "user": "dev-local", "firestore": False}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
