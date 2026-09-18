"""Domain exceptions for the Door subsystem.

The prediction path used to raise SystemExit for bad input, which is right for a
CLI and wrong for anything that embeds it: SystemExit inherits from
BaseException, so a UI's `except Exception` misses it and the process dies
instead of showing the message. These are ordinary exceptions; predict.py's
main() catches them and exits 1 with the same text, so CLI behaviour is
unchanged.
"""

from __future__ import annotations


class DoorError(Exception):
    """Base class for every Door subsystem error."""


class DoorInputError(DoorError):
    """The supplied stream cannot be processed.

    Missing or unreadable file, wrong columns, no data rows, unparseable
    timestamps. The message is written for a non-technical reader and is safe to
    show verbatim in a UI.
    """


class DoorModelError(DoorError):
    """The trained model is missing or unusable."""
