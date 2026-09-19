r"""Nebula condition-monitoring API.

Run from this directory:

    ..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

Must be 127.0.0.1:8000 and mounted under /api: Frontend/vite.config.ts proxies
/api there, which is also why there is no CORS middleware -- every request the
browser makes is same-origin.

See README.md in this directory for the full design.
"""

from __future__ import annotations

import logging
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if settings.local_dev_mode:
        log.warning(
            "LOCAL_DEV_MODE is enabled: Firebase authentication, Firestore "
            "cache and run history are disabled. Never deploy this mode."
        )
    else:
        # Fails loudly and deliberately in normal mode. Every protected route
        # requires a verified token, so a server that cannot verify tokens is
        # not partially useful.
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

    # Local mode has no identity store or run history. Omit those routes
    # instead of exposing endpoints that could only fail against a null DB.
    if not settings.local_dev_mode:
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

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
