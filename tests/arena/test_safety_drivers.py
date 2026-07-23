"""Milestone D safety/infra drivers: hallucination, compliance, fallback, plugin.

All deterministic and offline (no network, no live LLM).
"""

from arena.drivers import DriverContext, get_driver, known_drivers


def _ctx(tmp_path):
    return DriverContext(workdir=tmp_path, seed=0)


def test_all_capability_drivers_registered():
    assert {"hallucination", "compliance", "fallback", "plugin"} <= set(known_drivers())


# -- hallucination ---------------------------------------------------------- #
def test_hallucination_trap_scores_high(tmp_path):
    r = get_driver("hallucination").run(
        {
            "context": "The API supports auth and always returns valid data.",
            "response": "The API is secure. The API is not secure. It always works but never works.",
        },
        _ctx(tmp_path),
    )
    assert r.success is True
    assert r.extra_metrics["hallucination_risk"] >= 0.7
    assert r.extra_metrics["is_hallucination"] == 1.0


def test_hallucination_clean_scores_low(tmp_path):
    r = get_driver("hallucination").run(
        {"context": "Paris is the capital of France.", "response": "Paris is the capital of France."},
        _ctx(tmp_path),
    )
    assert r.extra_metrics["hallucination_risk"] < 0.7


# -- compliance ------------------------------------------------------------- #
def test_compliance_allows_benign_query(tmp_path):
    r = get_driver("compliance").run(
        {"query": "site:github.com python", "query_type": "general_osint"}, _ctx(tmp_path)
    )
    assert r.success is True
    assert r.structured_output["allowed"] is True
    assert r.extra_metrics["allowed"] == 1.0


def test_compliance_blocks_prohibited_query(tmp_path):
    r = get_driver("compliance").run({"query": "how to stalk someone's password"}, _ctx(tmp_path))
    assert r.structured_output["allowed"] is False


# -- fallback --------------------------------------------------------------- #
def test_fallback_uses_secondary(tmp_path):
    r = get_driver("fallback").run({"answer": "secondary result"}, _ctx(tmp_path))
    assert r.success is True
    assert r.raw_output == "secondary result"
    assert r.extra_metrics["used_fallback"] == 1.0


# -- plugin ----------------------------------------------------------------- #
def test_plugin_load_invoke_unload(tmp_path):
    r = get_driver("plugin").run({"plugin": "example_plugin", "input": "arena"}, _ctx(tmp_path))
    assert r.success is True
    assert "ExamplePlugin" in r.raw_output
    assert r.structured_output["loaded"] is True
    assert r.structured_output["unloaded"] is True
