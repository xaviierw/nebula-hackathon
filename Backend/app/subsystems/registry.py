"""The subsystem registry -- the one place a new model gets wired in.

Adding a finished subsystem is a ONE-LINE change here: swap its
NotImplementedRunner for the real runner. No router changes, no route changes.
It inherits auth, caching, history and error mapping automatically.
"""

from __future__ import annotations

import logging

from ..errors import NotFoundError
from .acv.runner import AcvRunner
from .base import SubsystemRunner
from .door.runner import DoorRunner
from .rail.runner import RailRunner

from .shm.runner import ShmRunner
from .stubs import NotImplementedRunner

log = logging.getLogger(__name__)

_RUNNERS: dict[str, SubsystemRunner] = {}


def register(runner: SubsystemRunner) -> None:
    _RUNNERS[runner.id] = runner


def get_runner(subsystem_id: str) -> SubsystemRunner:
    try:
        return _RUNNERS[subsystem_id]
    except KeyError:
        raise NotFoundError(f"Unknown subsystem: {subsystem_id}") from None


def all_runners() -> list[SubsystemRunner]:
    return list(_RUNNERS.values())


def load_all() -> None:
    """Load every runner at startup.

    One subsystem failing must never take down the others, so a raising load()
    is logged and marked unavailable rather than propagated.
    """
    for runner in _RUNNERS.values():
        try:
            runner.load()
        except Exception as exc:
            log.exception("Subsystem %s failed to load", runner.id)
            runner.available = False
            runner.unavailable_reason = f"{runner.name} failed to load: {exc}"


# --- Registration -------------------------------------------------------
# Ids must match SubsystemId in Frontend/src/subsystems.ts exactly.
#
# To wire up a finished subsystem, replace its line here. For example:
#     from .acv.runner import AcvRunner
#     register(AcvRunner())

register(DoorRunner())
register(AcvRunner())
register(RailRunner())
register(ShmRunner())
