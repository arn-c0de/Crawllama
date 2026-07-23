"""Hallucination-guard driver — deterministic, offline.

Runs the real :class:`core.hallu_detect.HallucinationDetector` with fact-checking
disabled (the only network path), so a trap response with internal contradictions
against a grounding context yields a deterministic HIGH hallucination risk. The
risk is reported as ``hallucination_risk`` (higher == worse), matching the audit
naming (plan §17).
"""

from __future__ import annotations

from typing import Any

from arena.drivers.base import Driver, DriverContext, DriverResult
from core import telemetry


class HallucinationDriver(Driver):
    name = "hallucination"

    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        from core.hallu_detect import HallucinationDetector

        response = str(scenario_input.get("response", ""))
        grounding = str(scenario_input.get("context", ""))
        detector = HallucinationDetector({"fact_checking_enabled": False})

        with telemetry.span("hallucination.checked"):
            result = detector.detect(response, grounding)

        risk = float(result.confidence_score)
        return DriverResult(
            success=True,
            raw_output=result.risk_level,
            structured_output=result.to_dict(),
            extra_metrics={
                "hallucination_risk": risk,
                "is_hallucination": 1.0 if result.is_hallucination else 0.0,
            },
        )
