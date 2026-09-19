r"""FastAPI entry point for Rail Corrugation inference.

Run locally from this directory with:

    .venv\Scripts\python.exe -m uvicorn main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, AsyncIterator, BinaryIO, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

if __package__:
    from .predictor import analyse_file, load_rail_model
else:
    from predictor import analyse_file, load_rail_model


MAX_UPLOAD_BYTES = 100 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024


class VibrationMeasurements(BaseModel):
    rms_median: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    rms_max: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    abs_peak_max: Annotated[float, Field(ge=0, allow_inf_nan=False)]


class RailEvidence(BaseModel):
    samples_per_sensor: int
    column_count: int
    duration_seconds: float
    vibration_sensors_per_side: int
    feature_count: int
    side_i: VibrationMeasurements
    side_ii: VibrationMeasurements


class RailAnalysis(BaseModel):
    file_id: str
    prediction: Literal["Normal", "Side I", "Side II"]
    evidence: RailEvidence


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Fail at startup if the model or its pinned dependencies are unavailable."""
    load_rail_model()
    yield


app = FastAPI(title="Nebula Rail Corrugation API", lifespan=lifespan)


def _copy_upload(source: BinaryIO, destination: Path) -> None:
    total = 0
    with destination.open("wb") as output:
        while chunk := source.read(COPY_CHUNK_BYTES):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="The uploaded CSV is larger than the 100 MB limit.",
                )
            output.write(chunk)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/rail-corrugation/predict", response_model=RailAnalysis)
def predict_rail_corrugation(
    file: Annotated[UploadFile, File(description="One Rail Corrugation sensor CSV")],
) -> RailAnalysis:
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a Rail Corrugation CSV file to analyse.",
        )
    if Path(filename).suffix.lower() != ".csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{filename}: expected a sensor recording in CSV format.",
        )

    with TemporaryDirectory(prefix="rail-corrugation-upload-") as directory:
        upload_path = Path(directory) / filename
        _copy_upload(file.file, upload_path)
        try:
            result = analyse_file(upload_path)
        except (FileNotFoundError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    return RailAnalysis.model_validate(result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
