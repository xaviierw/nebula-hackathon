"""SHM HTTP adapter. Start with uvicorn api:app --app-dir Backend/SHM."""
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from inference import DEFAULT_MODEL, MAX_UPLOAD_BYTES, Predictor, validate_filename


def create_app(model_path=DEFAULT_MODEL):
    @asynccontextmanager
    async def lifespan(app):
        # Fail at startup if the packaged artifact is absent or incompatible.
        app.state.predictor = Predictor(model_path)
        app.state.prediction_slots = asyncio.Semaphore(2)
        yield

    app = FastAPI(title="NebulaX SHM inference", lifespan=lifespan)

    @app.get('/api/shm/health')
    def health(request: Request):
        predictor = request.app.state.predictor
        return dict(status='ready', model_id=predictor.model_id,
                    observations=predictor.observations, max_upload_bytes=MAX_UPLOAD_BYTES)

    @app.post('/api/shm/predict')
    async def predict(request: Request, file: UploadFile = File(...)):
        try:
            validate_filename(file.filename)
            if file.size is not None and file.size > MAX_UPLOAD_BYTES:
                raise HTTPException(413, 'Each recording must be no larger than 16 MiB.')
            async with request.app.state.prediction_slots:
                raw = await file.read(MAX_UPLOAD_BYTES + 1)
                if len(raw) > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, 'Each recording must be no larger than 16 MiB.')
                # Keep CPU-heavy counting off the async server event loop.
                return await run_in_threadpool(request.app.state.predictor.predict, raw, file.filename)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            await file.close()

    return app


app = create_app()
