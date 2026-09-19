"""The contract every subsystem runner implements.

A runner is the adapter between one subsystem's own prediction code and this
API. It is the ONLY API-side file a subsystem author writes -- everything else
(auth, caching, history, error mapping, routing) is shared and comes for free.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel

UploadMode = Literal["stream", "per-file"]


class SubsystemRunner(ABC):
    # Must match SubsystemId in Frontend/src/subsystems.ts exactly, hyphen and
    # all: door, acv, rail-corrugation, shm. It is the URL slug on both sides.
    id: str
    name: str

    # "stream"   one continuous recording per upload; many result rows (Door).
    # "per-file" one result row per file; a submission CSV needs many files,
    #            so these use /predict-batch. The frontend reads this to decide
    #            whether its dropzone accepts multiple files.
    upload_mode: UploadMode = "per-file"

    response_model: type[BaseModel] | None = None

    # Set by load(). Never set these by hand at class level in a real runner.
    available: bool = False
    unavailable_reason: str | None = None
    model_version: str = "unavailable"

    @abstractmethod
    def load(self) -> None:
        """Called once at startup. Load model artifacts here, not per request.

        Must NOT raise for a recoverable condition such as a missing model
        file. Set available=False and unavailable_reason instead, so one
        subsystem being uninstalled never takes down the other three.
        """

    @abstractmethod
    def run(self, raw: bytes, filename: str) -> dict:
        """Bytes in, JSON-ready dict out.

        Pure: no file IO, no Firestore, no printing, no sys.exit. Runs in a
        worker thread, so it may block.

        Raise your subsystem's own <X>InputError for anything the user could
        fix (wrong columns, empty file, unparseable timestamps) -- its message
        is shown to them verbatim. Raise <X>ModelError for a broken or missing
        model.
        """

    def info(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "available": self.available,
            "reason": self.unavailable_reason,
            "model_version": self.model_version,
            "upload_mode": self.upload_mode,
        }
