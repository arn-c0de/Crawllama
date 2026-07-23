"""Evidence-first replay (plan §20).

Tools acquire a normalised :class:`EvidenceSnapshot` (URL, retrieval time, HTTP
status/content-type, content digest, sanitised text, provider, errors, cassette
version). One or more code/model profiles then *reason over the exact same
evidence*, which is what makes before/after and A/B comparisons defensible.

In ``pure``/``replay`` fixture modes an unexpected network call is a hard failure,
enforced by :func:`block_network`.
"""

from arena.evidence.guard import NetworkAccessError, block_network
from arena.evidence.model import EvidenceSnapshot, evidence_set_hash

__all__ = [
    "EvidenceSnapshot",
    "NetworkAccessError",
    "block_network",
    "evidence_set_hash",
]
