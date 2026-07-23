"""Atomic run store round-trips and immutability guarantees."""

import os
import stat

from arena.schema import (
    MetricBundle,
    Profile,
    RunManifest,
    RunResult,
    RunSummary,
    ScenarioScore,
)
from arena.store import ArenaStore


def _make_run(run_id="01TESTRUN0000000000000000"):
    profile = Profile(id="mock", provider="mock", model="mock")
    manifest = RunManifest(
        run_id=run_id,
        created_at="2026-07-23T00:00:00+00:00",
        git_sha="deadbeef",
        git_dirty=False,
        config_hash="sha256:abc",
        profile=profile,
        suite_id="smoke",
        scenario_set_hash="sha256:def",
        seed=0,
        host={},
    )
    result = RunResult(
        run_id=run_id,
        scenario_id="s1",
        driver="mock",
        raw_output="ok",
        metrics=MetricBundle(latency_ms=1.0, success=True),
        score=ScenarioScore(passed=True),
    )
    summary = RunSummary(
        run_id=run_id,
        created_at=manifest.created_at,
        git_sha="deadbeef",
        git_dirty=False,
        profile_id="mock",
        provider="mock",
        model="mock",
        suite_id="smoke",
        scenario_count=1,
        passed=1,
        failed=0,
        mean_latency_ms=1.0,
    )
    return manifest, [result], summary


def test_write_run_is_atomic_and_complete(tmp_path):
    store = ArenaStore(tmp_path)
    manifest, results, summary = _make_run()
    run_dir = store.write_run(manifest, results, summary, events=[])

    assert (run_dir / "COMPLETE").exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "results.jsonl").exists()
    assert store.is_complete(manifest.run_id)
    assert store.list_runs() == [manifest.run_id]
    # no leftover partial dir
    assert not (store.runs_dir / f"{manifest.run_id}.partial").exists()


def test_run_dir_and_files_are_owner_only(tmp_path):
    store = ArenaStore(tmp_path)
    manifest, results, summary = _make_run()
    run_dir = store.write_run(manifest, results, summary, events=[])
    assert stat.S_IMODE(os.stat(run_dir).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(run_dir / "manifest.json").st_mode) == 0o600


def test_read_back_matches_written(tmp_path):
    store = ArenaStore(tmp_path)
    manifest, results, summary = _make_run()
    store.write_run(manifest, results, summary, events=[])

    assert store.read_manifest(manifest.run_id).run_id == manifest.run_id
    assert store.read_summary(manifest.run_id).passed == 1
    back = store.read_results(manifest.run_id)
    assert len(back) == 1 and back[0].scenario_id == "s1"
    assert [s.run_id for s in store.iter_index()] == [manifest.run_id]


def test_incomplete_dir_is_ignored(tmp_path):
    store = ArenaStore(tmp_path)
    partial = store.runs_dir / "01ABANDONED0000000000000000.partial"
    partial.mkdir(parents=True)
    assert store.list_runs() == []
    assert "01ABANDONED0000000000000000.partial" in store.find_incomplete()
