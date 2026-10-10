"""Hallucination detector orchestrator and factory helpers."""
import logging
import re
import time
from typing import Any

from core.hallu.constants import (
    CITATION_PATTERNS,
    CONTRADICTORY_PATTERN_PAIRS,
    FACTUAL_CLAIM_PATTERNS,
    SEVERITY_WEIGHTS,
    SPECIFIC_INFO_PATTERNS,
    VAGUE_LANGUAGE_PATTERNS,
)
from core.hallu.context_analyzer import ContextAnalyzer
from core.hallu.fact_checker import FactChecker
from core.hallu.result import HallucinationResult

logger = logging.getLogger("crawllama")


class HallucinationDetector:
    """Main hallucination detection system."""
    
    def __init__(self, config: dict[str, Any] = None):
        """
        Initialize hallucination detector.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Core settings
        self.enabled = self.config.get("enabled", True)
        self.detection_level = self.config.get("detection_level", "medium")  # low, medium, high
        self.fact_checking_enabled = self.config.get("fact_checking_enabled", True)
        self.context_analysis_enabled = self.config.get("context_analysis_enabled", True)
        
        # Quality thresholds
        self.hallucination_threshold = self.config.get("hallucination_threshold", 0.7)
        self.context_alignment_threshold = self.config.get("context_alignment_threshold", 0.4)
        self.fact_confidence_threshold = self.config.get("fact_confidence_threshold", 0.6)
        
        # Performance settings
        self.max_processing_time = self.config.get("max_processing_time", 10.0)  # seconds
        self.cache_enabled = self.config.get("cache_enabled", True)
        self.batch_size = self.config.get("batch_size", 5)
        
        # Initialize components
        self.fact_checker = FactChecker(self.config.get("fact_checker", {}))
        self.context_analyzer = ContextAnalyzer(self.config.get("context_analyzer", {}))
        
        # Statistics
        self.stats = {
            "total_checks": 0,
            "hallucinations_detected": 0,
            "avg_processing_time": 0.0,
            "fact_checks_performed": 0
        }
        
        logger.info(f"Hallucination detector initialized (level: {self.detection_level})")
    
    def detect(self, response: str, context: str = "", metadata: dict[str, Any] = None) -> HallucinationResult:
        """
        Detect hallucinations in LLM response.
        
        Args:
            response: LLM-generated response to analyze
            context: Original context/prompt
            metadata: Additional metadata (model, temperature, etc.)
            
        Returns:
            HallucinationResult with analysis details
        """
        start_time = time.time()

        if not self.enabled:
            return self._create_disabled_result()

        try:
            violations: list[dict[str, Any]] = []
            quality_metrics: dict[str, float] = {}

            # 1. Basic quality checks
            quality_metrics.update(self._analyze_basic_quality(response))

            # 2. Context alignment analysis
            context_analysis = self._run_context_analysis(response, context, violations, quality_metrics)

            # 3. Fact checking
            fact_check_results = self._run_fact_checking(response, violations)

            # 4. Pattern-based detection
            violations.extend(self._detect_hallucination_patterns(response, context))

            # 5. Calculate overall scores
            confidence_score = self._calculate_confidence_score(violations, quality_metrics)
            is_hallucination = confidence_score >= self.hallucination_threshold
            risk_level = self._determine_risk_level(confidence_score, violations)

            processing_time = time.time() - start_time
            self._update_statistics(is_hallucination, processing_time)

            return HallucinationResult(
                is_hallucination=is_hallucination,
                confidence_score=confidence_score,
                risk_level=risk_level,
                violations=violations,
                context_alignment=context_analysis.get("alignment_score", 1.0),
                fact_check_results=fact_check_results,
                quality_metrics=quality_metrics,
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"Hallucination detection failed: {e}")
            return self._create_error_result(e, time.time() - start_time)

    def _run_context_analysis(
        self,
        response: str,
        context: str,
        violations: list[dict[str, Any]],
        quality_metrics: dict[str, float]
    ) -> dict[str, Any]:
        """Analyze context alignment, recording metrics and violations in place.

        Returns the context analysis dictionary (empty if analysis was skipped).
        """
        if not (self.context_analysis_enabled and context):
            return {}

        context_analysis = self.context_analyzer.analyze_context_alignment(response, context)
        quality_metrics["context_alignment"] = context_analysis["alignment_score"]

        if context_analysis["alignment_score"] < self.context_alignment_threshold:
            violations.append({
                "type": "low_context_alignment",
                "severity": "medium",
                "score": context_analysis["alignment_score"],
                "details": context_analysis
            })

        return context_analysis

    def _run_fact_checking(self, response: str, violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Fact-check claims in the response, recording violations in place.

        Returns the list of fact-check results (empty if checking was skipped).
        """
        if not self.fact_checking_enabled:
            return []

        factual_claims = self._extract_factual_claims(response)
        if not factual_claims:
            return []

        fact_check_results = self.fact_checker.check_facts(factual_claims)
        self.stats["fact_checks_performed"] += len(fact_check_results)

        unverified_claims = [r for r in fact_check_results if not r["verified"]]
        if unverified_claims:
            violations.append({
                "type": "unverified_facts",
                "severity": "high",
                "count": len(unverified_claims),
                "claims": [c["claim"] for c in unverified_claims[:3]]  # Top 3
            })

        return fact_check_results

    def _update_statistics(self, is_hallucination: bool, processing_time: float) -> None:
        """Update running detection statistics after a completed check."""
        self.stats["total_checks"] += 1
        if is_hallucination:
            self.stats["hallucinations_detected"] += 1

        self.stats["avg_processing_time"] = (
            (self.stats["avg_processing_time"] * (self.stats["total_checks"] - 1) + processing_time)
            / self.stats["total_checks"]
        )

    def _create_error_result(self, error: Exception, processing_time: float) -> HallucinationResult:
        """Create result for a failed detection run."""
        return HallucinationResult(
            is_hallucination=False,
            confidence_score=0.0,
            risk_level="unknown",
            violations=[{
                "type": "detection_error",
                "severity": "low",
                "error": str(error)
            }],
            context_alignment=0.0,
            fact_check_results=[],
            quality_metrics={},
            processing_time=processing_time
        )

    def _create_disabled_result(self) -> HallucinationResult:
        """Create result for disabled detector."""
        return HallucinationResult(
            is_hallucination=False,
            confidence_score=0.0,
            risk_level="disabled",
            violations=[],
            context_alignment=1.0,
            fact_check_results=[],
            quality_metrics={},
            processing_time=0.0
        )
    
    def _analyze_basic_quality(self, response: str) -> dict[str, float]:
        """Analyze basic response quality metrics."""
        metrics = {}
        
        # Length analysis
        length = len(response.strip())
        metrics["response_length"] = length
        metrics["length_score"] = min(1.0, length / 500)  # Normalize to 500 chars
        
        # Repetition detection
        words = response.lower().split()
        if words:
            unique_words = set(words)
            repetition_score = len(unique_words) / len(words)
            metrics["repetition_score"] = repetition_score
        else:
            metrics["repetition_score"] = 0.0
            
        # Coherence indicators
        sentences = re.split(r'[.!?]+', response)
        metrics["sentence_count"] = len([s for s in sentences if s.strip()])
        
        # Vague language detection
        vague_count = sum(len(re.findall(pattern, response.lower())) for pattern in VAGUE_LANGUAGE_PATTERNS)
        metrics["vague_language_score"] = min(1.0, vague_count / 10)  # Normalize
        
        return metrics
    
    def _extract_factual_claims(self, response: str) -> list[str]:
        """Extract potential factual claims for verification."""
        # Split into sentences
        sentences = re.split(r'[.!?]+', response)
        
        factual_claims = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short sentences
                continue

            # Look for factual patterns (dates, numbers, specific names)
            has_factual_content = any(re.search(pattern, sentence, re.IGNORECASE)
                                    for pattern in FACTUAL_CLAIM_PATTERNS)

            if has_factual_content:
                factual_claims.append(sentence)

        return factual_claims[:5]  # Limit to top 5 claims
    
    def _detect_hallucination_patterns(self, response: str, context: str) -> list[dict[str, Any]]:
        """Detect common hallucination patterns."""
        violations = []
        violations.extend(self._find_citation_violations(response))
        violations.extend(self._find_unsupported_specifics(response, context))
        violations.extend(self._find_internal_contradictions(response))
        return violations

    @staticmethod
    def _find_citation_violations(response: str) -> list[dict[str, Any]]:
        """Find potentially fabricated citations or references."""
        violations = []
        for pattern in CITATION_PATTERNS:
            for match in re.finditer(pattern, response, re.IGNORECASE):
                violations.append({
                    "type": "potential_fabricated_citation",
                    "severity": "medium",
                    "text": match.group(0),
                    "position": match.start()
                })
        return violations

    @staticmethod
    def _find_unsupported_specifics(response: str, context: str) -> list[dict[str, Any]]:
        """Find overly specific information not supported by the context."""
        if not context:
            return []

        violations = []
        for pattern in SPECIFIC_INFO_PATTERNS:
            for match in re.finditer(pattern, response, re.IGNORECASE):
                # Check if this specific info is supported by context
                if match.group(0) not in context:
                    violations.append({
                        "type": "unsupported_specific_info",
                        "severity": "high",
                        "text": match.group(0),
                        "details": "Specific information not found in context"
                    })
        return violations

    @staticmethod
    def _find_internal_contradictions(response: str) -> list[dict[str, Any]]:
        """Find contradictory statements within the response."""
        violations = []
        response_lower = response.lower()

        for positive, negative in CONTRADICTORY_PATTERN_PAIRS:
            pos_matches = list(re.finditer(positive, response_lower))
            neg_matches = list(re.finditer(negative, response_lower))

            if pos_matches and neg_matches:
                violations.append({
                    "type": "internal_contradiction",
                    "severity": "high",
                    "details": f"Found both '{positive}' and '{negative}' patterns"
                })
        return violations

    def _calculate_confidence_score(self, violations: list[dict], quality_metrics: dict) -> float:
        """Calculate overall hallucination confidence score."""
        score = 0.0

        # Weight violations by severity
        for violation in violations:
            weight = SEVERITY_WEIGHTS.get(violation.get("severity", "medium"), 0.3)
            score += weight
            
        # Factor in quality metrics
        if "context_alignment" in quality_metrics:
            # Low context alignment increases hallucination score
            alignment_penalty = (1.0 - quality_metrics["context_alignment"]) * 0.4
            score += alignment_penalty
            
        if "repetition_score" in quality_metrics:
            # High repetition might indicate hallucination
            if quality_metrics["repetition_score"] < 0.5:
                score += 0.2
                
        if "vague_language_score" in quality_metrics:
            # Too much vague language might hide hallucinations
            if quality_metrics["vague_language_score"] > 0.7:
                score += 0.15
        
        return min(1.0, score)
    
    def _determine_risk_level(self, confidence_score: float, violations: list[dict]) -> str:
        """Determine risk level based on confidence and violations."""
        high_severity_count = sum(1 for v in violations if v.get("severity") == "high")
        
        if confidence_score >= 0.8 or high_severity_count >= 2:
            return "high"
        elif confidence_score >= 0.5 or high_severity_count >= 1:
            return "medium"
        else:
            return "low"
    
    def get_statistics(self) -> dict[str, Any]:
        """Get detection statistics."""
        return dict(self.stats)
    
    def reset_statistics(self):
        """Reset statistics."""
        self.stats = {
            "total_checks": 0,
            "hallucinations_detected": 0,
            "avg_processing_time": 0.0,
            "fact_checks_performed": 0
        }
        
    def update_config(self, config: dict[str, Any]):
        """Update detector configuration."""
        self.config.update(config)
        
        # Update core settings
        self.enabled = self.config.get("enabled", self.enabled)
        self.detection_level = self.config.get("detection_level", self.detection_level)
        self.hallucination_threshold = self.config.get("hallucination_threshold", self.hallucination_threshold)
        
        logger.info("Hallucination detector configuration updated")


# Default configuration
DEFAULT_CONFIG = {
    "enabled": True,
    "detection_level": "medium",
    "hallucination_threshold": 0.7,
    "context_alignment_threshold": 0.4,
    "fact_confidence_threshold": 0.6,
    "fact_checking_enabled": True,
    "context_analysis_enabled": True,
    "max_processing_time": 10.0,
    "cache_enabled": True,
    "batch_size": 5,
    "fact_checker": {
        "wikipedia_check": True,
        "web_search_check": False,
        "min_claim_length": 10
    },
    "context_analyzer": {
        "min_context_overlap": 0.3,
        "contradiction_threshold": 0.7
    }
}


def create_detector(config: dict[str, Any] = None) -> HallucinationDetector:
    """
    Create hallucination detector with configuration.
    
    Args:
        config: Configuration dictionary (uses defaults if None)
        
    Returns:
        Configured HallucinationDetector instance
    """
    if config is None:
        config = DEFAULT_CONFIG.copy()
    else:
        # Merge with defaults
        merged_config = DEFAULT_CONFIG.copy()
        merged_config.update(config)
        config = merged_config
        
    return HallucinationDetector(config)


# Global detector instance
_detector = None


def get_detector(config: dict[str, Any] = None) -> HallucinationDetector:
    """Get global hallucination detector instance."""
    global _detector
    if _detector is None:
        _detector = create_detector(config)
    return _detector


def detect_hallucination(response: str, context: str = "", config: dict[str, Any] = None) -> HallucinationResult:
    """
    Convenience function for hallucination detection.
    
    Args:
        response: LLM response to analyze
        context: Original context/prompt
        config: Optional configuration
        
    Returns:
        HallucinationResult
    """
    detector = get_detector(config)
    return detector.detect(response, context)
