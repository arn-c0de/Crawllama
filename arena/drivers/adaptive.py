"""Adaptive driver — deterministic escalation logic.

Exercises the real :class:`core.adaptive_hops.AdaptiveHopManager` escalation
decision path without any LLM or network call:

* ``force_complexity`` bypasses LLM-based complexity analysis
  (``decide_agent_strategy`` short-circuits when a level is forced), and
* ``system_monitor=None`` guarantees no resource-based downgrade,

so the outcome depends only on the supplied confidence and the manager's
thresholds. A low confidence drives repeated escalation LOW → MID → HIGH; the
driver records the real ``EscalationTrace`` (attempts, reasons, hop path) and
emits ``adaptive.decision`` / ``adaptive.escalated`` events.
"""

from __future__ import annotations

from typing import Any

from arena.drivers.base import Driver, DriverContext, DriverResult
from core import telemetry


class _NoLLM:
    """A stand-in LLM that must never be called in this deterministic path."""

    def generate(self, *args: Any, **kwargs: Any) -> str:  # pragma: no cover - guard
        raise RuntimeError("adaptive driver invoked the LLM; force_complexity should prevent this")


class AdaptiveDriver(Driver):
    name = "adaptive"

    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        from core.adaptive_hops import AdaptiveConfig, AdaptiveHopManager, ComplexityLevel

        query = str(scenario_input.get("query", ""))
        force = str(scenario_input.get("force_complexity", "low"))
        confidence = float(scenario_input.get("confidence", 0.3))
        enable = bool(scenario_input.get("enable_escalation", True))

        try:
            forced_level = ComplexityLevel(force)
        except ValueError:
            return DriverResult(success=False, error=f"invalid force_complexity: {force!r}")

        manager = AdaptiveHopManager(
            llm=_NoLLM(),
            config=AdaptiveConfig(enable_resource_monitoring=False),
            system_monitor=None,
        )

        strategy = manager.decide_agent_strategy(query, force_complexity=forced_level)
        hop_path = [strategy["complexity"]]
        reasons: list[str] = []
        attempts = 0

        if enable:
            attempt_count = 1
            while True:
                do_escalate, new_strategy = manager.should_escalate(
                    strategy, confidence=confidence, attempt_count=attempt_count
                )
                telemetry.emit(
                    "adaptive.decision",
                    **{
                        "from_complexity": strategy["complexity"],
                        "confidence": confidence,
                        "escalate": do_escalate,
                    },
                )
                if not do_escalate or new_strategy is None:
                    break
                reasons.append(str(new_strategy.get("escalation_reason")))
                telemetry.emit(
                    "adaptive.escalated",
                    **{"from": strategy["complexity"], "to": new_strategy["complexity"]},
                )
                strategy = new_strategy
                hop_path.append(strategy["complexity"])
                attempts += 1
                attempt_count += 1

        final_complexity = strategy["complexity"]
        escalated = attempts > 0
        return DriverResult(
            success=True,
            raw_output=f"{hop_path[0]} -> {final_complexity} (attempts={attempts})",
            structured_output={
                "initial_complexity": hop_path[0],
                "final_complexity": final_complexity,
                "escalated": escalated,
                "attempts": attempts,
                "reasons": reasons,
                "hop_path": hop_path,
                "final_agent": strategy.get("agent_type"),
            },
            escalated=escalated,
            escalation_attempts=attempts,
            final_complexity=final_complexity,
            extra_metrics={"escalated": 1.0 if escalated else 0.0},
        )
