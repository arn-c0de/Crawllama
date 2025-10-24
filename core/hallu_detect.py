"""Hallucination Detection Module for LLM Output Quality Control.

This module provides comprehensive hallucination detection capabilities
for validating LLM-generated content against context and external knowledge.
"""

import logging
import re
import json
import time
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher

# Optional imports
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False

try:
    import wikipedia
    WIKIPEDIA_AVAILABLE = True
except ImportError:
    wikipedia = None
    WIKIPEDIA_AVAILABLE = False

logger = logging.getLogger("crawllama")


@dataclass
class HallucinationResult:
    """Result of hallucination detection analysis."""
    is_hallucination: bool
    confidence_score: float  # 0.0 - 1.0
    risk_level: str  # "low", "medium", "high"
    violations: List[Dict[str, Any]]
    context_alignment: float  # How well response aligns with context
    fact_check_results: List[Dict[str, Any]]
    quality_metrics: Dict[str, float]
    processing_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class FactChecker:
    """External fact-checking against knowledge sources."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize fact checker."""
        self.config = config
        self.wikipedia_enabled = config.get("wikipedia_check", True)
        self.web_search_enabled = config.get("web_search_check", False)
        self.cache = {}
        
    def check_facts(self, claims: List[str]) -> List[Dict[str, Any]]:
        """
        Verify factual claims against external sources.
        
        Args:
            claims: List of factual claims to verify
            
        Returns:
            List of fact-check results
        """
        results = []
        
        for claim in claims:
            if len(claim.strip()) < 10:  # Skip very short claims
                continue
                
            result = {
                "claim": claim,
                "verified": False,
                "confidence": 0.0,
                "sources": [],
                "contradictions": []
            }
            
            # Wikipedia fact check
            if self.wikipedia_enabled:
                wiki_result = self._check_wikipedia(claim)
                result["sources"].extend(wiki_result["sources"])
                if wiki_result["verified"]:
                    result["verified"] = True
                    result["confidence"] = max(result["confidence"], wiki_result["confidence"])
                
            # Web search fact check (if enabled)
            if self.web_search_enabled:
                web_result = self._check_web_search(claim)
                result["sources"].extend(web_result["sources"])
                if web_result["verified"]:
                    result["verified"] = True
                    result["confidence"] = max(result["confidence"], web_result["confidence"])
                    
            results.append(result)
            
        return results
    
    def _check_wikipedia(self, claim: str) -> Dict[str, Any]:
        """Check claim against Wikipedia with timeout protection."""
        if not WIKIPEDIA_AVAILABLE:
            logger.debug("Wikipedia module not available")
            return {"verified": False, "confidence": 0.0, "sources": []}
            
        try:
            # Extract key terms from claim
            key_terms = self._extract_key_terms(claim)
            
            # Check cache first
            for term in key_terms[:2]:  # Reduced to 2 terms for speed
                if term in self.cache:
                    cached = self.cache[term]
                    similarity = self._calculate_similarity(claim.lower(), cached["content"].lower())
                    if similarity > 0.3:
                        return {
                            "verified": True,
                            "confidence": similarity,
                            "sources": [{
                                "type": "wikipedia",
                                "title": cached["title"],
                                "url": cached["url"],
                                "similarity": similarity
                            }]
                        }
                    continue
                    
                # Wikipedia search with error handling
                try:
                    # Set Wikipedia timeout
                    wikipedia.set_rate_limiting(True, min_wait=0.1)
                    search_results = wikipedia.search(term, results=1)  # Only 1 result
                    
                    if search_results:
                        try:
                            page = wikipedia.page(search_results[0])
                            content = page.content[:300]  # Small content for speed
                            
                            # Simple similarity check
                            similarity = self._calculate_similarity(claim.lower(), content.lower())
                            
                            if similarity > 0.3:  # Threshold for relevance
                                self.cache[term] = {
                                    "content": content,
                                    "url": page.url,
                                    "title": page.title
                                }
                                
                                return {
                                    "verified": True,
                                    "confidence": similarity,
                                    "sources": [{
                                        "type": "wikipedia",
                                        "title": page.title,
                                        "url": page.url,
                                        "similarity": similarity
                                    }]
                                }
                                
                        except (wikipedia.exceptions.DisambiguationError, 
                                wikipedia.exceptions.PageError,
                                wikipedia.exceptions.WikipediaException):
                            # Skip problematic pages
                            continue
                            
                except Exception as e:
                    logger.debug(f"Wikipedia search failed for '{term}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Wikipedia fact check failed: {e}")
            
        return {"verified": False, "confidence": 0.0, "sources": []}
    
    def _check_web_search(self, claim: str) -> Dict[str, Any]:
        """Check claim via web search (placeholder for integration)."""
        # Placeholder for web search integration
        # Could integrate with DuckDuckGo, Google Custom Search, etc.
        return {"verified": False, "confidence": 0.0, "sources": []}
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms from text for fact checking."""
        # Remove common words and extract meaningful terms
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "is", "are", "was", "were", "be", "been", "have",
            "has", "had", "do", "does", "did", "will", "would", "could", "should"
        }
        
        # Extract words (alphanumeric, 3+ chars)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter out stop words and get unique terms
        key_terms = list(set(word for word in words if word not in stop_words))
        
        # Sort by length (longer terms often more specific)
        return sorted(key_terms, key=len, reverse=True)
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity score."""
        return SequenceMatcher(None, text1, text2).ratio()


class ContextAnalyzer:
    """Analyze response alignment with provided context."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize context analyzer."""
        self.config = config
        self.min_context_overlap = config.get("min_context_overlap", 0.3)
        self.contradiction_threshold = config.get("contradiction_threshold", 0.7)
        
    def analyze_context_alignment(self, response: str, context: str) -> Dict[str, Any]:
        """
        Analyze how well response aligns with provided context.
        
        Args:
            response: LLM-generated response
            context: Original context/prompt
            
        Returns:
            Context alignment analysis
        """
        if not context.strip():
            return {
                "alignment_score": 1.0,  # No context to contradict
                "missing_context": [],
                "contradictions": [],
                "coverage": 1.0
            }
            
        # Extract key concepts from context and response
        context_concepts = self._extract_concepts(context)
        response_concepts = self._extract_concepts(response)
        
        # Calculate coverage (how many context concepts are addressed)
        covered_concepts = context_concepts.intersection(response_concepts)
        coverage = len(covered_concepts) / len(context_concepts) if context_concepts else 1.0
        
        # Find missing important concepts
        missing_concepts = context_concepts - response_concepts
        
        # Detect potential contradictions
        contradictions = self._detect_contradictions(response, context)
        
        # Calculate overall alignment score
        alignment_score = coverage * (1.0 - len(contradictions) * 0.2)
        alignment_score = max(0.0, min(1.0, alignment_score))
        
        return {
            "alignment_score": alignment_score,
            "missing_context": list(missing_concepts),
            "contradictions": contradictions,
            "coverage": coverage
        }
    
    def _extract_concepts(self, text: str) -> Set[str]:
        """Extract key concepts from text."""
        # Simple concept extraction (could be enhanced with NLP)
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        
        # Filter out common words
        stop_words = {
            "this", "that", "with", "from", "they", "them", "their", "there",
            "where", "when", "what", "which", "while", "would", "could", "should",
            "about", "above", "after", "again", "against", "before", "below",
            "between", "during", "until", "under", "over"
        }
        
        return set(word for word in words if word not in stop_words)
    
    def _detect_contradictions(self, response: str, context: str) -> List[Dict[str, str]]:
        """Detect potential contradictions between response and context."""
        contradictions = []
        
        # Simple negation detection
        negation_patterns = [
            (r"not\s+(\w+)", r"\1"),
            (r"no\s+(\w+)", r"\1"),
            (r"never\s+(\w+)", r"\1"),
            (r"cannot\s+(\w+)", r"can \1"),
            (r"isn't\s+(\w+)", r"is \1"),
            (r"aren't\s+(\w+)", r"are \1"),
            (r"wasn't\s+(\w+)", r"was \1"),
            (r"weren't\s+(\w+)", r"were \1")
        ]
        
        response_lower = response.lower()
        context_lower = context.lower()
        
        for neg_pattern, pos_pattern in negation_patterns:
            neg_matches = re.finditer(neg_pattern, response_lower)
            
            for match in neg_matches:
                negated_concept = match.group(1)
                
                # Check if positive form exists in context
                if re.search(rf'\b{negated_concept}\b', context_lower):
                    contradictions.append({
                        "type": "negation_conflict",
                        "response_phrase": match.group(0),
                        "context_conflict": negated_concept,
                        "severity": "medium"
                    })
                    
        return contradictions


class HallucinationDetector:
    """Main hallucination detection system."""
    
    def __init__(self, config: Dict[str, Any] = None):
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
    
    def detect(self, response: str, context: str = "", metadata: Dict[str, Any] = None) -> HallucinationResult:
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
            # Initialize result
            violations = []
            fact_check_results = []
            quality_metrics = {}
            
            # 1. Basic quality checks
            quality_metrics.update(self._analyze_basic_quality(response))
            
            # 2. Context alignment analysis
            context_analysis = {}
            if self.context_analysis_enabled and context:
                context_analysis = self.context_analyzer.analyze_context_alignment(response, context)
                quality_metrics["context_alignment"] = context_analysis["alignment_score"]
                
                # Check for context violations
                if context_analysis["alignment_score"] < self.context_alignment_threshold:
                    violations.append({
                        "type": "low_context_alignment",
                        "severity": "medium",
                        "score": context_analysis["alignment_score"],
                        "details": context_analysis
                    })
            
            # 3. Fact checking
            if self.fact_checking_enabled:
                factual_claims = self._extract_factual_claims(response)
                if factual_claims:
                    fact_check_results = self.fact_checker.check_facts(factual_claims)
                    self.stats["fact_checks_performed"] += len(fact_check_results)
                    
                    # Analyze fact check results
                    unverified_claims = [r for r in fact_check_results if not r["verified"]]
                    if unverified_claims:
                        violations.append({
                            "type": "unverified_facts",
                            "severity": "high",
                            "count": len(unverified_claims),
                            "claims": [c["claim"] for c in unverified_claims[:3]]  # Top 3
                        })
            
            # 4. Pattern-based detection
            pattern_violations = self._detect_hallucination_patterns(response, context)
            violations.extend(pattern_violations)
            
            # 5. Calculate overall scores
            confidence_score = self._calculate_confidence_score(violations, quality_metrics)
            is_hallucination = confidence_score >= self.hallucination_threshold
            risk_level = self._determine_risk_level(confidence_score, violations)
            
            # Update statistics
            self.stats["total_checks"] += 1
            if is_hallucination:
                self.stats["hallucinations_detected"] += 1
                
            processing_time = time.time() - start_time
            self.stats["avg_processing_time"] = (
                (self.stats["avg_processing_time"] * (self.stats["total_checks"] - 1) + processing_time)
                / self.stats["total_checks"]
            )
            
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
            processing_time = time.time() - start_time
            
            return HallucinationResult(
                is_hallucination=False,
                confidence_score=0.0,
                risk_level="unknown",
                violations=[{
                    "type": "detection_error",
                    "severity": "low",
                    "error": str(e)
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
    
    def _analyze_basic_quality(self, response: str) -> Dict[str, float]:
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
        vague_patterns = [
            r'\b(maybe|perhaps|possibly|might|could be|seems like|appears to)\b',
            r'\b(I think|I believe|I guess|probably|likely)\b',
            r'\b(some|many|several|various|numerous)\b'
        ]
        
        vague_count = sum(len(re.findall(pattern, response.lower())) for pattern in vague_patterns)
        metrics["vague_language_score"] = min(1.0, vague_count / 10)  # Normalize
        
        return metrics
    
    def _extract_factual_claims(self, response: str) -> List[str]:
        """Extract potential factual claims for verification."""
        # Split into sentences
        sentences = re.split(r'[.!?]+', response)
        
        factual_claims = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short sentences
                continue
                
            # Look for factual patterns (dates, numbers, specific names)
            factual_patterns = [
                r'\b(in \d{4}|\d{4}s?)\b',  # Years
                r'\b\d+(\.\d+)?\s*(percent|%|million|billion|thousand)\b',  # Numbers with units
                r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # Proper names (simplified)
                r'\b(located in|founded in|established in|created by)\b',  # Factual relationships
            ]
            
            has_factual_content = any(re.search(pattern, sentence, re.IGNORECASE) 
                                    for pattern in factual_patterns)
            
            if has_factual_content:
                factual_claims.append(sentence)
                
        return factual_claims[:5]  # Limit to top 5 claims
    
    def _detect_hallucination_patterns(self, response: str, context: str) -> List[Dict[str, Any]]:
        """Detect common hallucination patterns."""
        violations = []
        
        # Pattern 1: Fabricated citations or references
        citation_patterns = [
            r'\b(according to|as reported by|studies show|research indicates)\b',
            r'\b(Source:|Reference:|Citation:)\b',
            r'\[\d+\]|\(\d{4}\)',  # Citation markers
        ]
        
        for pattern in citation_patterns:
            matches = re.finditer(pattern, response, re.IGNORECASE)
            for match in matches:
                violations.append({
                    "type": "potential_fabricated_citation",
                    "severity": "medium",
                    "text": match.group(0),
                    "position": match.start()
                })
        
        # Pattern 2: Overly specific information without context support
        if context:
            specific_patterns = [
                r'\b\d{1,2}:\d{2}\s*(AM|PM)\b',  # Specific times
                r'\b\$\d+(\.\d{2})?\b',  # Exact prices
                r'\b\d+(\.\d+)?%\b',  # Exact percentages
            ]
            
            for pattern in specific_patterns:
                matches = re.finditer(pattern, response, re.IGNORECASE)
                for match in matches:
                    # Check if this specific info is supported by context
                    if match.group(0) not in context:
                        violations.append({
                            "type": "unsupported_specific_info",
                            "severity": "high",
                            "text": match.group(0),
                            "details": "Specific information not found in context"
                        })
        
        # Pattern 3: Contradictory statements within response
        contradictory_pairs = [
            (r'\b(is|are)\b', r'\b(is not|are not|isn\'t|aren\'t)\b'),
            (r'\b(can|will)\b', r'\b(cannot|can\'t|will not|won\'t)\b'),
            (r'\b(always)\b', r'\b(never)\b'),
            (r'\b(all)\b', r'\b(none|no)\b'),
        ]
        
        for positive, negative in contradictory_pairs:
            pos_matches = list(re.finditer(positive, response.lower()))
            neg_matches = list(re.finditer(negative, response.lower()))
            
            if pos_matches and neg_matches:
                violations.append({
                    "type": "internal_contradiction",
                    "severity": "high",
                    "details": f"Found both '{positive}' and '{negative}' patterns"
                })
        
        return violations
    
    def _calculate_confidence_score(self, violations: List[Dict], quality_metrics: Dict) -> float:
        """Calculate overall hallucination confidence score."""
        score = 0.0
        
        # Weight violations by severity
        severity_weights = {"low": 0.1, "medium": 0.3, "high": 0.6}
        
        for violation in violations:
            weight = severity_weights.get(violation.get("severity", "medium"), 0.3)
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
    
    def _determine_risk_level(self, confidence_score: float, violations: List[Dict]) -> str:
        """Determine risk level based on confidence and violations."""
        high_severity_count = sum(1 for v in violations if v.get("severity") == "high")
        
        if confidence_score >= 0.8 or high_severity_count >= 2:
            return "high"
        elif confidence_score >= 0.5 or high_severity_count >= 1:
            return "medium"
        else:
            return "low"
    
    def get_statistics(self) -> Dict[str, Any]:
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
        
    def update_config(self, config: Dict[str, Any]):
        """Update detector configuration."""
        self.config.update(config)
        
        # Update core settings
        self.enabled = self.config.get("enabled", self.enabled)
        self.detection_level = self.config.get("detection_level", self.detection_level)
        self.hallucination_threshold = self.config.get("hallucination_threshold", self.hallucination_threshold)
        
        logger.info(f"Hallucination detector configuration updated")


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


def create_detector(config: Dict[str, Any] = None) -> HallucinationDetector:
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


def get_detector(config: Dict[str, Any] = None) -> HallucinationDetector:
    """Get global hallucination detector instance."""
    global _detector
    if _detector is None:
        _detector = create_detector(config)
    return _detector


def detect_hallucination(response: str, context: str = "", config: Dict[str, Any] = None) -> HallucinationResult:
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