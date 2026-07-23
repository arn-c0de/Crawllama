"""Latency collector.

Derives run-local timing from the event stream. The arena deliberately does not
use the process-global ``PerformanceTracker`` as its source of truth (plan §17):
it uses run-scoped durations captured on each event.
"""

from __future__ import annotations

from arena.schema import Event


def llm_latency_ms(events: list[Event]) -> float:
    """Total wall time spent in ``llm.completed`` events, in milliseconds."""
    total_ns = sum(e.duration_ns for e in events if e.name == "llm.completed")
    return total_ns / 1_000_000.0
