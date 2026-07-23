"""Scoring: deterministic rules gating for Milestone A.

Later milestones add pointwise/pairwise LLM-as-judge grading, calibration and
paired statistics (plan §22). Milestone A is rules-only so the regression gate is
fully deterministic and CI-safe.
"""

from arena.scoring.rules import score_scenario

__all__ = ["score_scenario"]
