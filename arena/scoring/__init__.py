"""Scoring: deterministic rules gating for Milestone A.

Later milestones add pointwise/pairwise LLM-as-judge grading, calibration and
paired statistics (plan §22). Milestone A is rules-only so the regression gate is
fully deterministic and CI-safe.
"""

from arena.scoring.rules import score_scenario

# Bump when the scoring policy (gate semantics / metric handling) changes in a
# way that makes scores non-comparable across runs. Part of the comparison
# fingerprint so a comparator refuses to compare runs scored differently.
SCORING_POLICY_VERSION = 1


def policy_fingerprint() -> str:
    """Stable fingerprint of the active scoring policy (plan §21 'scorer')."""
    from arena.config import content_hash

    return content_hash({"scorer": "rules", "version": SCORING_POLICY_VERSION})


__all__ = ["SCORING_POLICY_VERSION", "policy_fingerprint", "score_scenario"]
