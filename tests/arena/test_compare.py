"""Before/after comparator: regression gate, comparability refusal, reporting."""

import copy

import pytest

from arena.compare import ComparabilityError, ComparisonReport, compare_runs, comparison_dimensions
from arena.report import to_json, to_markdown
from arena.runner import ArenaRunner
from arena.schema import Profile
from arena.store import ArenaStore


def _runner(tmp_path):
    return ArenaRunner(ArenaStore(tmp_path))


def _mock():
    return Profile(id="mock", provider="mock", model="mock")


def _two_runs(tmp_path):
    runner = _runner(tmp_path)
    b = runner.run_suite("smoke", _mock())
    a = runner.run_suite("smoke", _mock())
    return b, a


def test_identical_runs_no_regression(tmp_path):
    (mb, rb, _), (ma, ra, _) = _two_runs(tmp_path)
    rep = compare_runs(mb, rb, ma, ra, varying="code")
    assert rep.regression is False
    assert rep.loss == 0
    assert rep.tie == len(rep.scenarios)


def test_intentional_regression_is_caught(tmp_path):
    (mb, rb, _), (ma, ra, _) = _two_runs(tmp_path)
    ra = copy.deepcopy(ra)
    for r in ra:
        if r.scenario_id == "tool.cache_hit.v1":
            r.score.passed = False
    rep = compare_runs(mb, rb, ma, ra, varying="code")
    assert rep.regression is True
    assert "tool.cache_hit.v1" in rep.regressions
    assert rep.loss == 1


def test_improvement_detected(tmp_path):
    (mb, rb, _), (ma, ra, _) = _two_runs(tmp_path)
    rb = copy.deepcopy(rb)
    for r in rb:
        if r.scenario_id == "memory.roundtrip.v1":
            r.score.passed = False  # failed before -> passes after
    rep = compare_runs(mb, rb, ma, ra, varying="code")
    assert rep.regression is False
    assert "memory.roundtrip.v1" in rep.improvements
    assert rep.win == 1


def test_comparability_refusal_on_scorer_mismatch(tmp_path):
    (mb, rb, _), (ma, ra, _) = _two_runs(tmp_path)
    ma = ma.model_copy(update={"scorer_hash": "sha256:OTHER"})
    with pytest.raises(ComparabilityError) as exc:
        compare_runs(mb, rb, ma, ra, varying="code")
    assert "scorer" in str(exc.value)
    # override allows it through
    rep = compare_runs(mb, rb, ma, ra, varying="code", allow_mismatch={"scorer"})
    assert isinstance(rep, ComparisonReport)


def test_code_comparison_allows_differing_code(tmp_path):
    (mb, rb, _), (ma, ra, _) = _two_runs(tmp_path)
    ma = ma.model_copy(update={"git_sha": "differentsha", "git_dirty": True})
    # code is the varying dimension -> not a refusal
    rep = compare_runs(mb, rb, ma, ra, varying="code")
    assert rep.dimensions_before["code"] != rep.dimensions_after["code"]


def test_model_comparison_refuses_differing_code(tmp_path):
    (mb, rb, _), (ma, ra, _) = _two_runs(tmp_path)
    ma = ma.model_copy(update={"git_sha": "differentsha"})
    with pytest.raises(ComparabilityError):
        compare_runs(mb, rb, ma, ra, varying="model")


def test_dimensions_reflect_dirty_and_model():
    from arena.manifest import build_manifest

    m = build_manifest(profile=_mock(), suite_id="smoke", scenario_set=[{"id": "a"}])
    dims = comparison_dimensions(m)
    assert dims["model"] == "mock:mock"
    assert dims["code"].endswith("+dirty") == m.git_dirty


def test_report_renders_md_and_json(tmp_path):
    (mb, rb, _), (ma, ra, _) = _two_runs(tmp_path)
    ra = copy.deepcopy(ra)
    for r in ra:
        if r.scenario_id == "tool.operators.v1":
            r.score.passed = False
    rep = compare_runs(mb, rb, ma, ra, varying="code")
    md = to_markdown(rep)
    assert "REGRESSION" in md
    assert "tool.operators.v1" in md
    assert "## Regressions (1)" in md
    js = to_json(rep)
    assert '"regression": true' in js
