"""Tournament ranking + budget-aware partial completion (offline)."""

import copy

from arena.budget import Budget, BudgetTracker
from arena.runner import ArenaRunner
from arena.schema import Profile
from arena.store import ArenaStore
from arena.tournament import run_tournament, to_json, to_markdown


def _run(tmp_path, profile_id):
    runner = ArenaRunner(ArenaStore(tmp_path / profile_id))
    prof = Profile(id=profile_id, provider="mock", model=profile_id)
    m, r, _ = runner.run_suite("smoke", prof, persist=False)
    return m, r


def test_tournament_ranks_and_separates_hard_gates(tmp_path):
    m_a, r_a = _run(tmp_path, "alpha")
    m_b, r_b = _run(tmp_path, "beta")
    # Degrade beta's soft signal on one scenario so alpha ranks higher.
    r_b = copy.deepcopy(r_b)
    r_b[0].metrics.extra["answer_quality"] = 0.0

    report = run_tournament("smoke", {"alpha": (m_a, r_a), "beta": (m_b, r_b)})
    assert len(report.standings) == 2
    assert report.standings[0].rank == 1
    # hard-gate pass rate is a separate, visible field
    for s in report.standings:
        assert 0.0 <= s.hard_gate_pass_rate <= 1.0
        assert s.scenario_count == len(r_a)
    assert report.incomplete is False


def test_tournament_budget_exhaustion_marks_incomplete(tmp_path):
    m_a, r_a = _run(tmp_path, "alpha")
    m_b, r_b = _run(tmp_path, "beta")
    m_c, r_c = _run(tmp_path, "gamma")

    tracker = BudgetTracker(Budget(max_llm_calls=2))  # only 2 profiles can be scored

    def charge(_results):
        tracker.charge(calls=1)

    report = run_tournament(
        "smoke",
        {"alpha": (m_a, r_a), "beta": (m_b, r_b), "gamma": (m_c, r_c)},
        budget=tracker,
        cost_per_profile=charge,
    )
    assert report.incomplete is True
    assert report.incomplete_reason and "budget" in report.incomplete_reason
    assert len(report.standings) == 2  # partial results


def test_tournament_report_renders(tmp_path):
    m_a, r_a = _run(tmp_path, "alpha")
    report = run_tournament("smoke", {"alpha": (m_a, r_a)})
    md = to_markdown(report)
    assert "Arena tournament" in md
    assert "hard-gate pass" in md
    assert '"suite_id": "smoke"' in to_json(report)
