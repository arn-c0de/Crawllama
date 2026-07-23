"""Model-arena tournament / leaderboard (plan §11, §16, §22).

Ranks N profiles that ran the *same* suite. Hard-gate pass rates are reported
**separately** from the composite ranking — a composite never hides a hard
failure. V1 uses per-scenario soft signals and win/tie/loss, not Elo (deferred).

If a :class:`arena.budget.BudgetTracker` is supplied (representing judge cost),
scoring stops cleanly on :class:`arena.budget.BudgetExhausted`, returning partial
standings with ``incomplete=True``.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from arena.budget import BudgetExhausted, BudgetTracker
from arena.schema import RunManifest, RunResult


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileStanding(_Strict):
    profile_id: str
    provider: str
    model: str
    scenario_count: int
    hard_gate_passed: int
    hard_gate_pass_rate: float
    composite_score: float
    per_category: dict[str, float] = Field(default_factory=dict)
    rank: int = 0


class TournamentReport(_Strict):
    suite_id: str
    standings: list[ProfileStanding] = Field(default_factory=list)
    incomplete: bool = False
    incomplete_reason: str | None = None
    budget: dict[str, float] | None = None


def _soft_signal(r: RunResult) -> float:
    """A per-result soft quality signal in [0,1], independent of the hard gate."""
    m = r.metrics
    for key in ("judge_score", "answer_quality"):
        if key in m.extra:
            return float(m.extra[key])
    if m.coverage is not None:
        return float(m.coverage)
    if m.final_confidence is not None:
        return float(m.final_confidence)
    return 1.0 if r.score.passed else 0.0


def _standing(profile_id: str, manifest: RunManifest, results: list[RunResult]) -> ProfileStanding:
    n = len(results)
    passed = sum(1 for r in results if r.score.passed)
    composite = (sum(_soft_signal(r) for r in results) / n) if n else 0.0

    # per-category hard-gate pass rate (category derived from scenario id prefix)
    cat_counts: dict[str, list[int]] = {}
    for r in results:
        cat = r.scenario_id.split(".")[0]
        cat_counts.setdefault(cat, []).append(1 if r.score.passed else 0)
    per_category = {c: sum(v) / len(v) for c, v in cat_counts.items()}

    return ProfileStanding(
        profile_id=profile_id,
        provider=manifest.profile.provider,
        model=manifest.profile.model,
        scenario_count=n,
        hard_gate_passed=passed,
        hard_gate_pass_rate=(passed / n) if n else 0.0,
        composite_score=composite,
        per_category=per_category,
    )


def run_tournament(
    suite_id: str,
    runs_by_profile: dict[str, tuple[RunManifest, list[RunResult]]],
    *,
    budget: BudgetTracker | None = None,
    cost_per_profile: Callable[[list[RunResult]], None] | None = None,
) -> TournamentReport:
    """Rank profiles by composite score after reporting hard gates separately."""
    standings: list[ProfileStanding] = []
    incomplete = False
    reason: str | None = None

    for profile_id, (manifest, results) in runs_by_profile.items():
        if budget is not None and cost_per_profile is not None:
            try:
                cost_per_profile(results)
            except BudgetExhausted as exc:
                incomplete = True
                reason = str(exc)
                break
        standings.append(_standing(profile_id, manifest, results))

    # Rank by composite (desc); hard-gate pass rate stays a separate visible column.
    standings.sort(key=lambda s: s.composite_score, reverse=True)
    for i, s in enumerate(standings, start=1):
        s.rank = i

    return TournamentReport(
        suite_id=suite_id,
        standings=standings,
        incomplete=incomplete,
        incomplete_reason=reason,
        budget=budget.snapshot() if budget else None,
    )


def to_markdown(report: TournamentReport) -> str:
    lines = ["# Arena tournament", ""]
    lines.append(f"**suite:** `{report.suite_id}`")
    if report.incomplete:
        lines.append(f"**⚠️ INCOMPLETE:** {report.incomplete_reason}")
    lines.append("")
    lines.append("Ranking is by composite score; hard-gate pass rate is shown separately and is never")
    lines.append("hidden inside the composite.")
    lines.append("")
    lines.append("| rank | profile | composite | hard-gate pass | model |")
    lines.append("|---|---|---|---|---|")
    for s in report.standings:
        lines.append(
            f"| {s.rank} | `{s.profile_id}` | {s.composite_score:.3f} | "
            f"{s.hard_gate_passed}/{s.scenario_count} ({s.hard_gate_pass_rate:.0%}) | {s.model} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def to_json(report: TournamentReport, *, indent: int = 2) -> str:
    import json

    return json.dumps(report.model_dump(), indent=indent)
