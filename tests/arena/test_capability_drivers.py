"""Milestone B capability drivers: osint (pure) + agent/multihop (fake-LLM)."""

from arena.collectors import UsageTotals, collect_usage
from arena.drivers import DriverContext, get_driver, known_drivers
from arena.events import EventCollector
from arena.schema import Event


def _ctx(tmp_path):
    return DriverContext(workdir=tmp_path, seed=0)


def test_registry_has_all_milestone_b_drivers():
    assert set(known_drivers()) == {"mock", "tool", "memory", "adaptive", "osint", "agent", "multihop"}


# -- osint ------------------------------------------------------------------ #
def test_osint_email_validate(tmp_path):
    good = get_driver("osint").run(
        {"module": "email", "op": "validate", "value": "a@example.com", "expected_fields": ["valid"]},
        _ctx(tmp_path),
    )
    assert good.success and good.structured_output["valid"] is True
    assert good.coverage == 1.0
    bad = get_driver("osint").run(
        {"module": "email", "op": "validate", "value": "nope"}, _ctx(tmp_path)
    )
    assert bad.structured_output["valid"] is False


def test_osint_ip_validate(tmp_path):
    r = get_driver("osint").run({"module": "ip", "op": "validate", "value": "8.8.8.8"}, _ctx(tmp_path))
    assert r.success and r.structured_output["valid"] is True
    assert "IPv4" in r.structured_output["type"]


def test_osint_unknown_op_fails(tmp_path):
    r = get_driver("osint").run({"module": "email", "op": "bogus", "value": "a@b.com"}, _ctx(tmp_path))
    assert r.success is False


# -- agent (real SearchAgent + fake LLM, offline) --------------------------- #
def test_agent_driver_offline(tmp_path):
    with EventCollector("s") as coll:
        r = get_driver("agent").run(
            {"query": "capital of france?", "answer": "Paris is the capital."}, _ctx(tmp_path)
        )
    assert r.success and "Paris" in r.raw_output
    # token usage captured from the fake LLM's llm.completed events
    usage = collect_usage(coll.events)
    assert usage.llm_calls >= 1
    assert usage.token_source == "estimated"
    # no user-data pollution: state stayed under the workdir
    assert (tmp_path / "session.json").exists()


# -- multihop (real graph + fake LLM, offline) ------------------------------ #
def test_multihop_driver_offline(tmp_path):
    r = get_driver("multihop").run(
        {"query": "linked entities?", "answer": "Synthesised answer.", "max_hops": 1},
        _ctx(tmp_path),
    )
    assert r.success and r.raw_output == "Synthesised answer."
    assert r.structured_output["confidence"] is not None


# -- usage collector edge cases --------------------------------------------- #
def test_collect_usage_empty():
    assert collect_usage([]) == UsageTotals(llm_calls=0, tokens_in=0, tokens_out=0, token_source=None)


def _llm_event(seq, source, ti=1, to=1):
    return Event(
        event_id=f"e{seq}",
        seq=seq,
        name="llm.completed",
        started_ns=0,
        attributes={
            "arena.token_source": source,
            "gen_ai.usage.input_tokens": ti,
            "gen_ai.usage.output_tokens": to,
        },
    )


def test_collect_usage_provider_only():
    u = collect_usage([_llm_event(0, "provider", 5, 7), _llm_event(1, "provider", 1, 2)])
    assert u.llm_calls == 2 and u.tokens_in == 6 and u.tokens_out == 9
    assert u.token_source == "provider"


def test_collect_usage_mixed_degrades_to_estimated():
    u = collect_usage([_llm_event(0, "provider"), _llm_event(1, "estimated")])
    assert u.token_source == "estimated"
