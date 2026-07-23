"""Before/after comparison and regression gating (plan §11, §21, §22).

Comparability is *field-specific*. A comparison varies exactly one dimension and
requires the others to match:

    code comparison  (before/after regression): code varies; model, scenarios,
                     scorer and evidence must match.
    model comparison (A/B):                      model varies; code, scenarios,
                     scorer and evidence must match.

If a required-equal dimension differs, the comparator **refuses** with a clear
message rather than silently comparing different meanings. ``--allow-mismatch``
overrides a specific dimension deliberately.

The unit of comparison is the paired scenario, not a global mean. A **hard-gate
regression** — a scenario that passed in *before* and fails in *after* — sets
``regression = True`` and fails the gate.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from arena.schema import RunManifest, RunResult

_DIMENSIONS = ("code", "model", "scenarios", "scorer", "evidence")


class ComparabilityError(ValueError):
    """Raised when runs cannot be compared along the requested axis."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScenarioDelta(_Strict):
    scenario_id: str
    before_passed: bool | None = None
    after_passed: bool | None = None
    status: str  # regressed | improved | unchanged_pass | unchanged_fail | added | removed
    before_latency_ms: float | None = None
    after_latency_ms: float | None = None
    latency_delta_ms: float | None = None


class ComparisonReport(_Strict):
    before_run_id: str
    after_run_id: str
    varying: str
    dimensions_before: dict[str, str]
    dimensions_after: dict[str, str]
    scenarios: list[ScenarioDelta] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    win: int = 0
    tie: int = 0
    loss: int = 0
    regression: bool = False


def comparison_dimensions(m: RunManifest) -> dict[str, str]:
    """The five comparison-identity dimensions of a run (plan §21)."""
    return {
        "code": m.git_sha + ("+dirty" if m.git_dirty else ""),
        "model": f"{m.profile.provider}:{m.profile.model}",
        "scenarios": m.scenario_set_hash,
        "scorer": m.scorer_hash or "none",
        "evidence": m.evidence_hash or "none",
    }


def _scenario_passed(results: list[RunResult]) -> bool:
    """A scenario passes only if every one of its repeats passed."""
    return bool(results) and all(r.score.passed for r in results)


def _mean_latency(results: list[RunResult]) -> float | None:
    if not results:
        return None
    return sum(r.metrics.latency_ms for r in results) / len(results)


def _group(results: list[RunResult]) -> dict[str, list[RunResult]]:
    grouped: dict[str, list[RunResult]] = {}
    for r in results:
        grouped.setdefault(r.scenario_id, []).append(r)
    return grouped


def compare_runs(
    before_manifest: RunManifest,
    before_results: list[RunResult],
    after_manifest: RunManifest,
    after_results: list[RunResult],
    *,
    varying: str = "code",
    allow_mismatch: set[str] | None = None,
) -> ComparisonReport:
    """Compare two runs, refusing incomparable ones unless overridden."""
    if varying not in _DIMENSIONS:
        raise ValueError(f"varying must be one of {_DIMENSIONS}, got {varying!r}")
    allow_mismatch = allow_mismatch or set()

    dims_b = comparison_dimensions(before_manifest)
    dims_a = comparison_dimensions(after_manifest)

    required_equal = [d for d in _DIMENSIONS if d != varying]
    mismatches = [
        d for d in required_equal if dims_b[d] != dims_a[d] and d not in allow_mismatch
    ]
    if mismatches:
        detail = "; ".join(f"{d}: {dims_b[d]!r} != {dims_a[d]!r}" for d in mismatches)
        raise ComparabilityError(
            f"cannot run a '{varying}' comparison: these dimensions differ but must match: {detail}. "
            f"Pass allow_mismatch={{{', '.join(repr(m) for m in mismatches)}}} to override."
        )

    before_by = _group(before_results)
    after_by = _group(after_results)
    all_ids = sorted(set(before_by) | set(after_by))

    deltas: list[ScenarioDelta] = []
    regressions: list[str] = []
    improvements: list[str] = []
    win = tie = loss = 0

    for sid in all_ids:
        b = before_by.get(sid)
        a = after_by.get(sid)
        bp = _scenario_passed(b) if b is not None else None
        ap = _scenario_passed(a) if a is not None else None
        bl = _mean_latency(b) if b else None
        al = _mean_latency(a) if a else None

        if b is None:
            status = "added"
        elif a is None:
            status = "removed"
        elif bp and not ap:
            status = "regressed"
            regressions.append(sid)
            loss += 1
        elif ap and not bp:
            status = "improved"
            improvements.append(sid)
            win += 1
        elif bp and ap:
            status = "unchanged_pass"
            tie += 1
        else:
            status = "unchanged_fail"
            tie += 1

        deltas.append(
            ScenarioDelta(
                scenario_id=sid,
                before_passed=bp,
                after_passed=ap,
                status=status,
                before_latency_ms=bl,
                after_latency_ms=al,
                latency_delta_ms=(al - bl) if (al is not None and bl is not None) else None,
            )
        )

    return ComparisonReport(
        before_run_id=before_manifest.run_id,
        after_run_id=after_manifest.run_id,
        varying=varying,
        dimensions_before=dims_b,
        dimensions_after=dims_a,
        scenarios=deltas,
        regressions=regressions,
        improvements=improvements,
        win=win,
        tie=tie,
        loss=loss,
        regression=bool(regressions),
    )
