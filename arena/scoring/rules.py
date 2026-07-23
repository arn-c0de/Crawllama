"""Deterministic, CI-safe rules scoring.

Hard gates are evaluated first (execution success, substring inclusion/exclusion,
required structured fields, expected escalation/cache behaviour). Metric bounds
are checked separately. A scenario *passes* only when **every** hard gate and
**every** metric bound passes — a hard failure is never averaged away inside a
composite (plan §22).
"""

from __future__ import annotations

from typing import Any

from arena.schema import GateResult, MetricBundle, Scenario, ScenarioScore


def _metric_values(metrics: MetricBundle) -> dict[str, float]:
    """Flatten the metric bundle into a name → value lookup for bound checks."""
    values: dict[str, float] = {}
    for name in (
        "latency_ms",
        "coverage",
        "final_confidence",
        "hallucination_risk",
        "context_utilisation",
        "tool_calls",
        "escalation_attempts",
        "cost_usd",
    ):
        v = getattr(metrics, name, None)
        if v is not None:
            values[name] = float(v)
    if metrics.tokens_in is not None:
        values["tokens_in"] = float(metrics.tokens_in)
    if metrics.tokens_out is not None:
        values["tokens_out"] = float(metrics.tokens_out)
    for name, v in metrics.extra.items():
        values[name] = float(v)
    return values


def score_scenario(
    scenario: Scenario,
    metrics: MetricBundle,
    raw_output: str,
    structured_output: dict[str, Any],
) -> ScenarioScore:
    gates: list[GateResult] = []
    exp = scenario.expect

    # -- hard gate: execution success ---------------------------------- #
    if exp.hard.success is not None:
        ok = metrics.success == exp.hard.success
        gates.append(
            GateResult(
                name="success",
                passed=ok,
                detail=f"expected success={exp.hard.success}, got {metrics.success}"
                + (f" ({metrics.error})" if metrics.error else ""),
            )
        )

    # -- hard gate: substring inclusion/exclusion ---------------------- #
    for needle in exp.hard.must_include:
        gates.append(
            GateResult(
                name=f"must_include:{needle}",
                passed=needle in raw_output,
                detail=f"'{needle}' {'found' if needle in raw_output else 'missing'} in output",
            )
        )
    for needle in exp.hard.must_not_include:
        present = needle in raw_output
        gates.append(
            GateResult(
                name=f"must_not_include:{needle}",
                passed=not present,
                detail=f"'{needle}' {'present' if present else 'absent'}",
            )
        )

    # -- hard gate: required structured fields ------------------------- #
    for field_name, required in exp.hard.expected_fields.items():
        if not required:
            continue
        present = bool(structured_output.get(field_name))
        gates.append(
            GateResult(
                name=f"field:{field_name}",
                passed=present,
                detail=f"structured field '{field_name}' {'present' if present else 'missing/falsy'}",
            )
        )

    # -- hard gate: escalation behaviour ------------------------------- #
    if exp.escalation is not None:
        esc = exp.escalation
        if esc.happened is not None:
            got = bool(metrics.escalated)
            gates.append(
                GateResult(
                    name="escalation.happened",
                    passed=got == esc.happened,
                    detail=f"expected escalated={esc.happened}, got {got}",
                )
            )
        if esc.final_complexity is not None:
            got_c = metrics.final_complexity
            gates.append(
                GateResult(
                    name="escalation.final_complexity",
                    passed=got_c == esc.final_complexity,
                    detail=f"expected final_complexity={esc.final_complexity}, got {got_c}",
                )
            )
        if esc.min_attempts is not None:
            got_a = metrics.escalation_attempts or 0
            gates.append(
                GateResult(
                    name="escalation.min_attempts",
                    passed=got_a >= esc.min_attempts,
                    detail=f"expected >= {esc.min_attempts} attempts, got {got_a}",
                )
            )

    # -- hard gate: cache behaviour ------------------------------------ #
    if exp.cache is not None:
        if exp.cache.hit is not None:
            got_h = bool(metrics.cache_hit)
            gates.append(
                GateResult(
                    name="cache.hit",
                    passed=got_h == exp.cache.hit,
                    detail=f"expected cache hit={exp.cache.hit}, got {got_h}",
                )
            )
        if exp.cache.miss is not None:
            got_m = metrics.cache_hit is False
            gates.append(
                GateResult(
                    name="cache.miss",
                    passed=got_m == exp.cache.miss,
                    detail=f"expected cache miss={exp.cache.miss}, got {got_m}",
                )
            )

    # -- metric bounds -------------------------------------------------- #
    metric_checks: list[GateResult] = []
    values = _metric_values(metrics)
    for name, bound in exp.metrics.items():
        if name not in values:
            metric_checks.append(
                GateResult(name=f"metric:{name}", passed=False, detail=f"metric '{name}' not measured")
            )
            continue
        v = values[name]
        ok = True
        parts = []
        if bound.min is not None:
            ok = ok and v >= bound.min
            parts.append(f">= {bound.min}")
        if bound.max is not None:
            ok = ok and v <= bound.max
            parts.append(f"<= {bound.max}")
        metric_checks.append(
            GateResult(name=f"metric:{name}", passed=ok, detail=f"{name}={v:g} (need {' and '.join(parts) or 'any'})")
        )

    passed = all(g.passed for g in gates) and all(m.passed for m in metric_checks)
    return ScenarioScore(passed=passed, gates=gates, metric_checks=metric_checks)
