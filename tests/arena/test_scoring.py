"""Rules scoring: hard gates first, metric bounds separate."""

from arena.schema import (
    CacheExpect,
    EscalationExpect,
    Expectation,
    HardExpect,
    MetricBound,
    MetricBundle,
    Scenario,
)
from arena.scoring import score_scenario


def _scenario(expect):
    return Scenario(id="t", driver="mock", expect=expect)


def test_success_gate_pass_and_fail():
    exp = Expectation(hard=HardExpect(success=True))
    good = score_scenario(_scenario(exp), MetricBundle(success=True), "", {})
    bad = score_scenario(_scenario(exp), MetricBundle(success=False, error="boom"), "", {})
    assert good.passed is True
    assert bad.passed is False
    assert any("boom" in g.detail for g in bad.gates)


def test_must_include_and_exclude():
    exp = Expectation(hard=HardExpect(must_include=["yes"], must_not_include=["ERROR"]))
    ok = score_scenario(_scenario(exp), MetricBundle(success=True), "yes it worked", {})
    bad = score_scenario(_scenario(exp), MetricBundle(success=True), "ERROR happened", {})
    assert ok.passed is True
    assert bad.passed is False


def test_metric_bound_missing_metric_fails():
    exp = Expectation(metrics={"coverage": MetricBound(min=0.5)})
    # coverage not set -> not measured -> fail
    res = score_scenario(_scenario(exp), MetricBundle(success=True), "", {})
    assert res.passed is False
    assert any("not measured" in m.detail for m in res.metric_checks)


def test_metric_bound_pass():
    exp = Expectation(metrics={"coverage": MetricBound(min=0.5, max=1.0)})
    res = score_scenario(_scenario(exp), MetricBundle(success=True, coverage=0.8), "", {})
    assert res.passed is True


def test_escalation_gate():
    exp = Expectation(escalation=EscalationExpect(happened=True, final_complexity="high", min_attempts=2))
    good = score_scenario(
        _scenario(exp),
        MetricBundle(success=True, escalated=True, final_complexity="high", escalation_attempts=2),
        "",
        {},
    )
    bad = score_scenario(
        _scenario(exp),
        MetricBundle(success=True, escalated=True, final_complexity="mid", escalation_attempts=1),
        "",
        {},
    )
    assert good.passed is True
    assert bad.passed is False


def test_cache_gate():
    exp = Expectation(cache=CacheExpect(hit=True))
    good = score_scenario(_scenario(exp), MetricBundle(success=True, cache_hit=True), "", {})
    bad = score_scenario(_scenario(exp), MetricBundle(success=True, cache_hit=False), "", {})
    assert good.passed is True
    assert bad.passed is False


def test_hard_failure_not_averaged_away():
    # A hard gate failure fails the scenario even if every metric passes.
    exp = Expectation(
        hard=HardExpect(success=True),
        metrics={"answer_quality": MetricBound(min=0.0)},
    )
    res = score_scenario(
        _scenario(exp),
        MetricBundle(success=False, extra={"answer_quality": 1.0}),
        "",
        {},
    )
    assert res.passed is False
