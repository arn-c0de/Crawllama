"""Hallucination detection package.

Split out of the former monolithic ``core/hallu_detect.py`` (which now re-exports
from here). Public API: :class:`HallucinationDetector`, :class:`HallucinationResult`,
:func:`create_detector`, :func:`get_detector`, :func:`detect_hallucination`.
"""
from core.hallu.cache import LRUCache
from core.hallu.context_analyzer import ContextAnalyzer
from core.hallu.detector import (
    DEFAULT_CONFIG,
    HallucinationDetector,
    create_detector,
    detect_hallucination,
    get_detector,
)
from core.hallu.fact_checker import FactChecker
from core.hallu.result import HallucinationResult

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
