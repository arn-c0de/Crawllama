"""Strict Pydantic models for scenarios, profiles, manifests, results and events.

All models use ``extra="forbid"`` so a typo in a checked-in scenario file is a
hard validation error rather than a silently ignored field. Everything here is
JSON-serialisable and versioned via :data:`arena.SCHEMA_VERSION`.

The scenario format is *driver-based* (plan §17): a scenario declares a
``driver`` plus a free-form ``input`` payload, so different capabilities (a raw
tool call, the memory store, the adaptive processor, …) can be exercised without
parsing human-formatted answers back into pseudo-structure.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from arena import SCHEMA_VERSION

FixtureMode = Literal["pure", "replay", "live"]
DriverName = Literal["mock", "tool", "memory", "adaptive", "agent", "multihop", "osint", "plugin"]


class _Strict(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Expectations                                                                 #
# --------------------------------------------------------------------------- #
class MetricBound(_Strict):
    """A numeric acceptance bound for a named metric (inclusive)."""

    min: float | None = None
    max: float | None = None


class EscalationExpect(_Strict):
    happened: bool | None = None
    final_complexity: str | None = None
    min_attempts: int | None = None


class CacheExpect(_Strict):
    hit: bool | None = None
    miss: bool | None = None


class HardExpect(_Strict):
    """Hard gates — any failure fails the scenario regardless of soft metrics."""

    success: bool | None = None
    must_include: list[str] = Field(default_factory=list)
    must_not_include: list[str] = Field(default_factory=list)
    expected_fields: dict[str, bool] = Field(default_factory=dict)


class Expectation(_Strict):
    hard: HardExpect = Field(default_factory=HardExpect)
    escalation: EscalationExpect | None = None
    cache: CacheExpect | None = None
    metrics: dict[str, MetricBound] = Field(default_factory=dict)


class Scenario(_Strict):
    schema_version: int = SCHEMA_VERSION
    id: str
    category: str = "misc"
    driver: DriverName
    input: dict[str, Any] = Field(default_factory=dict)
    fixture_mode: FixtureMode = "pure"
    expect: Expectation = Field(default_factory=Expectation)
    tags: list[str] = Field(default_factory=list)
    timeout_s: int = 120
    repeats: int = 1


class Suite(_Strict):
    """An ordered, named collection of scenario ids."""

    schema_version: int = SCHEMA_VERSION
    id: str
    description: str = ""
    scenarios: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Profiles & manifest                                                          #
# --------------------------------------------------------------------------- #
class Profile(_Strict):
    id: str
    provider: str = "mock"
    model: str = "mock"
    params: dict[str, Any] = Field(default_factory=dict)
    code_state: str = "WORKTREE"
    config_overrides: dict[str, Any] = Field(default_factory=dict)


class RunManifest(_Strict):
    """The reproducibility contract for a single run (plan §21)."""

    schema_version: int = SCHEMA_VERSION
    run_id: str
    created_at: str  # ISO-8601, injected (no wallclock in pure logic)
    git_sha: str
    git_dirty: bool
    config_hash: str
    profile: Profile
    suite_id: str
    scenario_set_hash: str
    seed: int
    host: dict[str, Any] = Field(default_factory=dict)
    worker_protocol_version: int = 1


# --------------------------------------------------------------------------- #
# Events (plan §19)                                                            #
# --------------------------------------------------------------------------- #
class Event(_Strict):
    event_id: str
    scenario_id: str | None = None
    parent_id: str | None = None
    seq: int
    name: str
    started_ns: int
    duration_ns: int = 0
    status: str = "ok"  # ok | error
    attributes: dict[str, Any] = Field(default_factory=dict)
    error_type: str | None = None


# --------------------------------------------------------------------------- #
# Metrics, scores & results                                                    #
# --------------------------------------------------------------------------- #
class MetricBundle(_Strict):
    latency_ms: float = 0.0
    tokens_in: int | None = None
    tokens_out: int | None = None
    token_source: Literal["provider", "estimated"] | None = None
    context_utilisation: float | None = None
    hallucination_risk: float | None = None  # higher == more risk (plan §17)
    final_confidence: float | None = None
    coverage: float | None = None
    tool_calls: int = 0
    cache_hit: bool | None = None
    escalated: bool | None = None
    escalation_attempts: int | None = None
    final_complexity: str | None = None
    cost_usd: float | None = None
    success: bool = False
    error: str | None = None
    # arbitrary driver-supplied task metrics used by rules scoring (0..1 scale)
    extra: dict[str, float] = Field(default_factory=dict)


class GateResult(_Strict):
    name: str
    passed: bool
    detail: str = ""


class ScenarioScore(_Strict):
    passed: bool
    gates: list[GateResult] = Field(default_factory=list)
    metric_checks: list[GateResult] = Field(default_factory=list)


class RunResult(_Strict):
    schema_version: int = SCHEMA_VERSION
    run_id: str
    scenario_id: str
    repeat_index: int = 0
    driver: str
    raw_output: str = ""
    structured_output: dict[str, Any] = Field(default_factory=dict)
    metrics: MetricBundle
    score: ScenarioScore
    events: list[Event] = Field(default_factory=list)


class RunSummary(_Strict):
    """One compact row per run for ``data/arena/index.jsonl``."""

    schema_version: int = SCHEMA_VERSION
    run_id: str
    created_at: str
    git_sha: str
    git_dirty: bool
    profile_id: str
    provider: str
    model: str
    suite_id: str
    scenario_count: int
    passed: int
    failed: int
    mean_latency_ms: float = 0.0
    config_hash: str = ""
