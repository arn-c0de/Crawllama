"""Hallucination detection — compatibility facade.

The implementation now lives in the :mod:`core.hallu` package. This module
re-exports the public API so existing imports (``from core.hallu_detect import
create_detector`` / ``HallucinationDetector`` / ``HallucinationResult`` / ...)
keep working.
"""
from core.hallu import (
    DEFAULT_CONFIG,
    ContextAnalyzer,
    FactChecker,
    HallucinationDetector,
    HallucinationResult,
    LRUCache,
    create_detector,
    detect_hallucination,
    get_detector,
)

__all__ = [
    "LRUCache",
    "ContextAnalyzer",
    "FactChecker",
    "HallucinationResult",
    "HallucinationDetector",
    "DEFAULT_CONFIG",
    "create_detector",
    "get_detector",
    "detect_hallucination",
]
