"""Fallback driver — deterministic, offline provider-fallback selection.

Drives the real :class:`core.fallback_manager.FallbackManager`: registers a
primary that always fails and a secondary that succeeds, then asserts the manager
fell back to the secondary and recorded the failure. No network — the manager
just invokes the callables it is given.
"""

from __future__ import annotations

from typing import Any

from arena.drivers.base import Driver, DriverContext, DriverResult
from core import telemetry


class FallbackDriver(Driver):
    name = "fallback"

    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        from core.fallback_manager import FallbackManager

        expected = str(scenario_input.get("answer", "secondary result"))

        def primary(*_a: Any, **_k: Any) -> str:
            raise RuntimeError("primary provider down")

        def secondary(*_a: Any, **_k: Any) -> str:
            return expected

        manager = FallbackManager()
        manager.register("arena_tool", primary, [secondary])

        with telemetry.span("fallback.executed"):
            result = manager.execute("arena_tool")

        stats = manager.get_stats("arena_tool")
        flat = _flatten_stats(stats)
        used_fallback = flat.get("fallback_success", 0) >= 1
        primary_failed = flat.get("primary_failures", 0) >= 1
        telemetry.emit("fallback.selected", **{"used_fallback": used_fallback})

        success = result == expected and used_fallback and primary_failed
        return DriverResult(
            success=success,
            raw_output=result,
            structured_output={"result": result, "stats": stats},
            extra_metrics={"used_fallback": 1.0 if used_fallback else 0.0},
        )


def _flatten_stats(stats: dict[str, Any]) -> dict[str, int]:
    """get_stats may return a flat dict or {name: {...}}; normalise to flat ints."""
    if stats and all(isinstance(v, dict) for v in stats.values()):
        # nested {name: {...}} -> merge the single strategy's stats
        merged: dict[str, int] = {}
        for inner in stats.values():
            for k, v in inner.items():
                if isinstance(v, int):
                    merged[k] = merged.get(k, 0) + v
        return merged
    return {k: v for k, v in stats.items() if isinstance(v, int)}
