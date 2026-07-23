"""Driver protocol and shared result type.

A *driver* adapts one CrawlLama capability to the arena's uniform contract: it
receives a scenario ``input`` dict plus an isolated :class:`DriverContext`, does
real work (calling production ``core/``/``tools/`` code — never re-implementing
it), emits telemetry events via :mod:`core.telemetry`, and returns a
:class:`DriverResult` the runner folds into a :class:`arena.schema.MetricBundle`.

Drivers must be deterministic given the same input + seed, and must not touch
global state — all filesystem state goes under ``context.workdir``.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DriverContext:
    """Per-scenario isolated execution context."""

    workdir: Path
    seed: int = 0
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def cache_dir(self) -> Path:
        return self.workdir / "cache"

    @property
    def memory_file(self) -> Path:
        return self.workdir / "memory.json"


@dataclass
class DriverResult:
    """Uniform output every driver returns; folded into a MetricBundle."""

    success: bool
    raw_output: str = ""
    structured_output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    # metric contributions (all optional)
    final_confidence: float | None = None
    coverage: float | None = None
    tool_calls: int = 0
    cache_hit: bool | None = None
    escalated: bool | None = None
    escalation_attempts: int | None = None
    final_complexity: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    token_source: str | None = None
    extra_metrics: dict[str, float] = field(default_factory=dict)


class Driver(abc.ABC):
    """Base class for all arena drivers."""

    #: stable driver name; must match the ``driver`` field in scenarios.
    name: str = ""

    @abc.abstractmethod
    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        """Execute the scenario and return a uniform result."""
        raise NotImplementedError
