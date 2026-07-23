"""Mock driver — canned, dependency-free, the CI anchor.

Produces a deterministic answer from the scenario ``input`` and, optionally,
emits synthetic telemetry events so the store/scoring/gate machinery can be
exercised with zero external dependencies (no network, no LLM, no chromadb).

Scenario ``input`` fields (all optional):
    answer: str            -> raw_output
    confidence: float      -> final_confidence
    coverage: float        -> coverage
    metrics: {name: float} -> extra_metrics (0..1 task metrics)
    emit_events: [str]     -> extra event names to emit (e.g. "cache.lookup")
    fail: bool             -> force success=False
    error: str             -> error message when fail is set
"""

from __future__ import annotations

from typing import Any

from arena.drivers.base import Driver, DriverContext, DriverResult
from core import telemetry


class MockDriver(Driver):
    name = "mock"

    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        telemetry.emit("agent.started", **{"arena.driver": self.name})
        answer = str(scenario_input.get("answer", ""))
        for name in scenario_input.get("emit_events", []) or []:
            telemetry.emit(str(name), **{"arena.synthetic": True})

        fail = bool(scenario_input.get("fail", False))
        metrics = {str(k): float(v) for k, v in (scenario_input.get("metrics") or {}).items()}
        result = DriverResult(
            success=not fail,
            raw_output=answer,
            structured_output={"answer": answer},
            error=str(scenario_input.get("error")) if fail else None,
            final_confidence=_maybe_float(scenario_input.get("confidence")),
            coverage=_maybe_float(scenario_input.get("coverage")),
            extra_metrics=metrics,
        )
        telemetry.emit("agent.completed", status="error" if fail else "ok", **{"arena.driver": self.name})
        return result


def _maybe_float(value: Any) -> float | None:
    return None if value is None else float(value)
