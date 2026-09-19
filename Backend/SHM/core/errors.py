"""Domain exceptions for the SHM subsystem.

Modelled on Backend/Door/core/errors.py, and for the same reason: the
prediction path must never raise SystemExit. SystemExit inherits from
BaseException, so an embedding caller's `except Exception` misses it and the
process dies instead of showing the message.
"""

from __future__ import annotations


class ShmError(Exception):
    """Base class for every SHM subsystem error."""


class ShmInputError(ShmError):
    """The supplied file cannot be processed.

    Wrong columns, no data rows, unparseable values. THE MESSAGE IS SHOWN TO
    THE USER VERBATIM -- write it for a non-technical reader. Multi-line is
    fine; the frontend renders it with whitespace-pre-line.
    """


class ShmModelError(ShmError):
    """The trained model is missing or unusable."""
