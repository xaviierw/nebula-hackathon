"""Domain exceptions for the ACV subsystem."""

from __future__ import annotations


class AcvError(Exception):
    """Base class for every ACV subsystem error."""


class AcvInputError(AcvError):
    """The supplied file cannot be processed.
    
    Shown verbatim to the end user in the frontend.
    """


class AcvModelError(AcvError):
    """The model config or parameters are missing or unusable."""