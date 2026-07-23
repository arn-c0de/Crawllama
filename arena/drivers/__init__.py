"""Driver registry.

Maps the ``driver`` name declared in a scenario to a :class:`Driver` instance.
Milestone A ships the four deterministic, network-/LLM-free drivers:
``mock``, ``tool``, ``memory`` and ``adaptive``. Later milestones add
``agent``, ``multihop`` and ``osint`` (which require the production instrumentation
seams and evidence replay).
"""

from __future__ import annotations

from arena.drivers.adaptive import AdaptiveDriver
from arena.drivers.base import Driver, DriverContext, DriverResult
from arena.drivers.memory import MemoryDriver
from arena.drivers.mock import MockDriver
from arena.drivers.tool import ToolDriver

_REGISTRY: dict[str, Driver] = {
    d.name: d
    for d in (MockDriver(), ToolDriver(), MemoryDriver(), AdaptiveDriver())
}


def get_driver(name: str) -> Driver:
    """Return the driver registered under *name*, or raise ``KeyError``."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown driver {name!r}; known: {sorted(_REGISTRY)}") from None


def known_drivers() -> list[str]:
    return sorted(_REGISTRY)


__all__ = [
    "Driver",
    "DriverContext",
    "DriverResult",
    "get_driver",
    "known_drivers",
]
