"""Adaptive driver — deterministic complexity-routing & escalation logic.

Exercises the real :class:`core.adaptive_hops.AdaptiveHopManager` without any
network call, in one of two modes:

**Escalation mode** (``force_complexity`` set) — the classic path:

* ``force_complexity`` bypasses LLM-based complexity analysis
  (``decide_agent_strategy`` short-circuits when a level is forced), and
* ``system_monitor=None`` guarantees no resource-based downgrade,

so the outcome depends only on the supplied confidence and the manager's
thresholds. A low confidence drives repeated escalation LOW → MID → HIGH; the
driver records the real ``EscalationTrace`` (attempts, reasons, hop path).

**Classification mode** (``classifier_response`` set, ``force_complexity``
omitted) — runs the *real* ``analyze_query_complexity`` offline by injecting a
:class:`FakeLLM` that returns a canned label (e.g. ``"LOW"``). This lets a CI
scenario assert routing decisions — e.g. that an explicit search query is never
routed to a tool-less LOW strategy even when the classifier LLM says ``LOW`` —
without a live model. ``use_tools`` and the resolved complexity are exposed in
``structured_output``.

Both modes emit ``adaptive.decision`` / ``adaptive.escalated`` events.
"""

from __future__ import annotations

from typing import Any

from arena.drivers._fakes import FakeLLM
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
        confidence = float(scenario_input.get("confidence", 0.3))
        enable = bool(scenario_input.get("enable_escalation", True))

        # Classification mode: no forced level, a deterministic classifier LLM,
        # so the real analyze_query_complexity (+ search-intent floor) runs.
        classifier_response = scenario_input.get("classifier_response")
        if classifier_response is not None:
            llm: Any = FakeLLM(str(classifier_response))
            forced_level = None
        else:
            llm = _NoLLM()
            force = str(scenario_input.get("force_complexity", "low"))
            try:
                forced_level = ComplexityLevel(force)
            except ValueError:
                return DriverResult(success=False, error=f"invalid force_complexity: {force!r}")

        manager = AdaptiveHopManager(
            llm=llm,
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
                "use_tools": bool(strategy.get("use_tools")),
                "complexity": strategy.get("complexity"),
            },
            escalated=escalated,
            escalation_attempts=attempts,
            final_complexity=final_complexity,
            extra_metrics={"escalated": 1.0 if escalated else 0.0},
        )
