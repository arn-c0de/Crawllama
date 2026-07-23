"""Paired statistics for stochastic scenarios (plan §22).

The unit of comparison is the paired scenario, not the global mean. For
stochastic scenarios (``repeats > 1``) we report median, dispersion and a paired
**bootstrap** confidence interval on the per-scenario deltas. A difference is
"significant" only when the CI excludes zero. Everything here is deterministic
given a seed — no numpy dependency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class WinTieLoss:
    win: int = 0
    tie: int = 0
    loss: int = 0


def win_tie_loss(deltas: list[float], eps: float = 1e-9) -> WinTieLoss:
    """Classify each paired delta as win (>0), tie (~0) or loss (<0)."""
    wtl = WinTieLoss()
    for d in deltas:
        if d > eps:
            wtl.win += 1
        elif d < -eps:
            wtl.loss += 1
        else:
            wtl.tie += 1
    return wtl


def median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def iqr(xs: list[float]) -> float:
    """Inter-quartile range as a dispersion measure (robust, no numpy)."""
    if len(xs) < 2:
        return 0.0
    s = sorted(xs)
    n = len(s)
    q1 = s[n // 4]
    q3 = s[(3 * n) // 4]
    return q3 - q1


def paired_deltas(before: list[float], after: list[float]) -> list[float]:
    """Element-wise after - before over paired observations."""
    if len(before) != len(after):
        raise ValueError("paired_deltas requires equal-length inputs")
    return [a - b for b, a in zip(before, after, strict=True)]


def paired_bootstrap_ci(
    deltas: list[float],
    *,
    n_resamples: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean of paired deltas (deterministic)."""
    if not deltas:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(deltas)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = [deltas[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = max(0, int((alpha / 2) * n_resamples))
    hi_idx = min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))
    return (means[lo_idx], means[hi_idx])


def ci_excludes_zero(ci: tuple[float, float]) -> bool:
    """True when the whole confidence interval is on one side of zero."""
    lo, hi = ci
    return lo > 0 or hi < 0
