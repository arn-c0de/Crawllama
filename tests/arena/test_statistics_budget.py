"""Paired statistics + budget caps (offline, deterministic)."""

import pytest

from arena.budget import Budget, BudgetExhausted, BudgetTracker
from arena.statistics import (
    ci_excludes_zero,
    iqr,
    median,
    paired_bootstrap_ci,
    paired_deltas,
    win_tie_loss,
)


# -- statistics ------------------------------------------------------------- #
def test_win_tie_loss():
    wtl = win_tie_loss([0.5, -0.2, 0.0, 0.3, -0.1])
    assert (wtl.win, wtl.tie, wtl.loss) == (2, 1, 2)


def test_median_and_iqr():
    assert median([3, 1, 2]) == 2
    assert median([1, 2, 3, 4]) == 2.5
    assert iqr([1, 2, 3, 4, 5, 6, 7, 8]) > 0


def test_paired_deltas_requires_equal_length():
    assert paired_deltas([1, 2], [2, 4]) == [1, 2]
    with pytest.raises(ValueError):
        paired_deltas([1], [1, 2])


def test_bootstrap_ci_deterministic_and_excludes_zero():
    deltas = [0.4, 0.5, 0.45, 0.55, 0.5]  # clearly positive
    ci1 = paired_bootstrap_ci(deltas, seed=7)
    ci2 = paired_bootstrap_ci(deltas, seed=7)
    assert ci1 == ci2  # deterministic
    assert ci_excludes_zero(ci1) is True


def test_bootstrap_ci_includes_zero_for_noisy():
    deltas = [0.5, -0.5, 0.4, -0.4, 0.1, -0.1]
    ci = paired_bootstrap_ci(deltas, seed=1)
    assert ci_excludes_zero(ci) is False


# -- budget ----------------------------------------------------------------- #
def test_budget_charges_within_cap():
    t = BudgetTracker(Budget(max_llm_calls=3, max_tokens=100))
    t.charge(calls=1, tokens=10)
    t.charge(calls=1, tokens=10)
    assert t.snapshot()["llm_calls"] == 2


def test_budget_raises_on_call_cap():
    t = BudgetTracker(Budget(max_llm_calls=2))
    t.charge(calls=1)
    t.charge(calls=1)
    with pytest.raises(BudgetExhausted) as exc:
        t.charge(calls=1)
    assert exc.value.limit == "llm_calls"


def test_budget_raises_on_cost_cap():
    t = BudgetTracker(Budget(max_cost_usd=0.05))
    t.charge(cost=0.04)
    with pytest.raises(BudgetExhausted):
        t.charge(cost=0.02)


def test_unlimited_budget_never_raises():
    t = BudgetTracker()  # all None
    for _ in range(1000):
        t.charge(calls=1, tokens=1000, cost=1.0)
    assert t.snapshot()["llm_calls"] == 1000
