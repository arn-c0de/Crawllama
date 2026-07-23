"""Suite orchestration.

Runs every scenario in a suite (honouring ``repeats``) against one profile with
isolated filesystem state per scenario, captures telemetry events, folds each
:class:`DriverResult` into a :class:`MetricBundle`, applies rules scoring and
writes one atomic run to the store.

State isolation: each scenario/repeat gets a fresh temp ``workdir`` so caches,
memory stores and any other on-disk state never leak across scenarios or into the
user's ``data/`` tree (plan §7).
"""

from __future__ import annotations

import tempfile
import time
from contextlib import nullcontext
from pathlib import Path

from arena.drivers import DriverContext, DriverResult, get_driver
from arena.events import EventCollector
from arena.evidence import block_network
from arena.loader import resolve_suite
from arena.manifest import build_manifest
from arena.schema import (
    Event,
    MetricBundle,
    Profile,
    RunManifest,
    RunResult,
    RunSummary,
    Scenario,
)
from arena.scoring import score_scenario
from arena.store import ArenaStore


class ArenaRunner:
    def __init__(self, store: ArenaStore | None = None) -> None:
        self.store = store or ArenaStore()

    def run_suite(
        self,
        suite_id: str,
        profile: Profile,
        seed: int = 0,
        persist: bool = True,
    ) -> tuple[RunManifest, list[RunResult], RunSummary]:
        scenarios = resolve_suite(suite_id)
        manifest = build_manifest(
            profile=profile,
            suite_id=suite_id,
            scenario_set=[s.model_dump() for s in scenarios],
            effective_config=profile.config_overrides,
            seed=seed,
        )

        results: list[RunResult] = []
        with tempfile.TemporaryDirectory(prefix="arena-run-") as tmp:
            root = Path(tmp)
            for scenario in scenarios:
                for repeat in range(max(1, scenario.repeats)):
                    results.append(
                        self._run_one(manifest.run_id, scenario, seed, root, repeat)
                    )

        summary = _summarise(manifest, profile, results)
        if persist:
            events = _flatten_events(results)
            self.store.write_run(manifest, results, summary, events=events)
        return manifest, results, summary

    # ------------------------------------------------------------------ #
    def _run_one(
        self,
        run_id: str,
        scenario: Scenario,
        seed: int,
        root: Path,
        repeat: int,
    ) -> RunResult:
        driver = get_driver(scenario.driver)
        workdir = root / _safe(scenario.id) / str(repeat)
        workdir.mkdir(parents=True, exist_ok=True)
        context = DriverContext(workdir=workdir, seed=seed)

        # Deterministic fixture modes must not touch the network; an unexpected
        # connection is a hard failure (plan §7, §20). `live` scenarios opt out.
        allow_hosts = set(scenario.input.get("allow_hosts", []) or [])
        guard = (
            block_network(allow_hosts)
            if scenario.fixture_mode in ("pure", "replay")
            else nullcontext()
        )

        collector = EventCollector(scenario.id)
        started = time.perf_counter()
        with collector:
            try:
                with guard:
                    result = driver.run(scenario.input, context)
            except Exception as exc:  # noqa: BLE001 - a driver crash is a failed scenario, not a crashed run
                result = DriverResult(success=False, error=f"{type(exc).__name__}: {exc}")
        latency_ms = (time.perf_counter() - started) * 1000.0

        metrics = _to_metrics(result, latency_ms)
        _enrich_from_events(metrics, collector.events)
        score = score_scenario(scenario, metrics, result.raw_output, result.structured_output)
        return RunResult(
            run_id=run_id,
            scenario_id=scenario.id,
            repeat_index=repeat,
            driver=scenario.driver,
            raw_output=result.raw_output,
            structured_output=result.structured_output,
            metrics=metrics,
            score=score,
            events=list(collector.events),
        )


def execute_scenario(scenario: Scenario, seed: int = 0, run_id: str = "worker") -> RunResult:
    """Run a single scenario in its own isolated temp dir (used by the worker)."""
    runner = ArenaRunner.__new__(ArenaRunner)  # no store needed for a one-shot
    with tempfile.TemporaryDirectory(prefix="arena-worker-") as tmp:
        return runner._run_one(run_id, scenario, seed, Path(tmp), 0)


def _enrich_from_events(metrics: MetricBundle, events: list[Event]) -> None:
    """Fold event-derived signals (token usage, tool calls) into the bundle.

    Driver-supplied values win; event-derived values fill the gaps. This lets a
    driver that just runs the real agent get token accounting "for free" from the
    instrumented LLM clients.
    """
    from arena.collectors import collect_usage

    usage = collect_usage(events)
    if usage.llm_calls:
        if metrics.tokens_in is None:
            metrics.tokens_in = usage.tokens_in
        if metrics.tokens_out is None:
            metrics.tokens_out = usage.tokens_out
        if metrics.token_source is None:
            metrics.token_source = usage.token_source
    if not metrics.tool_calls:
        metrics.tool_calls = sum(1 for e in events if e.name == "tool.started")


def _to_metrics(result: DriverResult, latency_ms: float) -> MetricBundle:
    return MetricBundle(
        latency_ms=latency_ms,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        token_source=result.token_source,
        final_confidence=result.final_confidence,
        coverage=result.coverage,
        tool_calls=result.tool_calls,
        cache_hit=result.cache_hit,
        escalated=result.escalated,
        escalation_attempts=result.escalation_attempts,
        final_complexity=result.final_complexity,
        success=result.success,
        error=result.error,
        extra=dict(result.extra_metrics),
    )


def _summarise(manifest: RunManifest, profile: Profile, results: list[RunResult]) -> RunSummary:
    passed = sum(1 for r in results if r.score.passed)
    failed = len(results) - passed
    mean_latency = (sum(r.metrics.latency_ms for r in results) / len(results)) if results else 0.0
    return RunSummary(
        run_id=manifest.run_id,
        created_at=manifest.created_at,
        git_sha=manifest.git_sha,
        git_dirty=manifest.git_dirty,
        profile_id=profile.id,
        provider=profile.provider,
        model=profile.model,
        suite_id=manifest.suite_id,
        scenario_count=len(results),
        passed=passed,
        failed=failed,
        mean_latency_ms=mean_latency,
        config_hash=manifest.config_hash,
    )


def _flatten_events(results: list[RunResult]) -> list[Event]:
    out: list[Event] = []
    for r in results:
        out.extend(r.events)
    return out


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
