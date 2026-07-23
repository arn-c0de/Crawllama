"""End-to-end runner + worker protocol, no network or LLM."""

from arena.loader import resolve_suite, validate_all
from arena.runner import ArenaRunner, execute_scenario
from arena.schema import Profile
from arena.store import ArenaStore
from arena.worker import handle_request


def _mock_profile():
    return Profile(id="mock", provider="mock", model="mock")


def test_all_fixtures_validate():
    cases, suites = validate_all()
    assert "smoke" in suites
    assert "adaptive.low_confidence_escalates.v1" in cases


def test_smoke_suite_all_pass_and_events_captured(tmp_path):
    store = ArenaStore(tmp_path)
    manifest, results, summary = ArenaRunner(store).run_suite("smoke", _mock_profile())

    assert summary.failed == 0
    assert summary.passed == summary.scenario_count == 5

    # real cache + escalation events must be present in the stored stream
    all_events = [e.name for r in results for e in r.events]
    assert "cache.lookup" in all_events
    assert "adaptive.escalated" in all_events

    # persisted atomically and indexed
    assert store.is_complete(manifest.run_id)
    assert [s.run_id for s in store.iter_index()] == [manifest.run_id]


def test_run_suite_without_persist_writes_nothing(tmp_path):
    store = ArenaStore(tmp_path)
    _, _, summary = ArenaRunner(store).run_suite("smoke", _mock_profile(), persist=False)
    assert summary.failed == 0
    assert store.list_runs() == []


def test_execute_single_scenario():
    scenario = resolve_suite("smoke")[0]
    result = execute_scenario(scenario)
    assert result.score.passed is True


def test_worker_ping_and_capabilities():
    assert handle_request({"op": "ping"})["pong"] is True
    caps = handle_request({"op": "capabilities"})
    assert set(caps["drivers"]) == {"mock", "tool", "memory", "adaptive"}


def test_worker_runs_scenario():
    resp = handle_request(
        {
            "op": "run_scenario",
            "scenario": {
                "id": "w1",
                "driver": "memory",
                "input": {"email": "w@example.com"},
                "expect": {"hard": {"success": True}},
            },
        }
    )
    assert resp["ok"] is True
    assert resp["result"]["score"]["passed"] is True


def test_worker_refuses_newer_protocol():
    resp = handle_request({"op": "ping", "protocol_version": 999})
    assert resp["ok"] is False
    assert "protocol_version" in resp["error"]


def test_worker_rejects_invalid_scenario():
    resp = handle_request({"op": "run_scenario", "scenario": {"id": "x", "driver": "bogus"}})
    assert resp["ok"] is False
