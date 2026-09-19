"""Placeholder runner for a subsystem nobody has built yet."""

from __future__ import annotations

from ..errors import SubsystemNotImplementedError
from .base import SubsystemRunner, UploadMode


class NotImplementedRunner(SubsystemRunner):
    """Registers a subsystem so its routes exist and return an honest 501.

    The routes existing matters: the frontend can show the subsystem, call it,
    and render a real message, rather than getting a 404 that looks like a
    routing bug.
    """

    def __init__(self, id: str, name: str, upload_mode: UploadMode = "per-file") -> None:
        self.id = id
        self.name = name
        self.upload_mode = upload_mode
        self.available = False
        self.unavailable_reason = f"The {name} model has not been built yet."
        self.model_version = "unavailable"

    def load(self) -> None:
        return None

    def run(self, raw: bytes, filename: str) -> dict:
        raise SubsystemNotImplementedError(self.name)
