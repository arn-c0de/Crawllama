"""Context-alignment analysis for hallucination detection."""
import logging
import re
from typing import Any

from core.hallu.constants import CONCEPT_STOP_WORDS, NEGATION_PATTERNS

logger = logging.getLogger("crawllama")


class ContextAnalyzer:
    """Analyze response alignment with provided context."""
    
    def __init__(self, config: dict[str, Any]):
        """Initialize context analyzer."""
        self.config = config
        self.min_context_overlap = config.get("min_context_overlap", 0.3)
        self.contradiction_threshold = config.get("contradiction_threshold", 0.7)
        
    def analyze_context_alignment(self, response: str, context: str) -> dict[str, Any]:
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
    
    def _extract_concepts(self, text: str) -> set[str]:
        """Extract key concepts from text."""
        # Simple concept extraction (could be enhanced with NLP)
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())

        return set(word for word in words if word not in CONCEPT_STOP_WORDS)
    
    def _detect_contradictions(self, response: str, context: str) -> list[dict[str, str]]:
        """Detect potential contradictions between response and context."""
        contradictions = []

        response_lower = response.lower()
        context_lower = context.lower()

        # Simple negation detection
        for neg_pattern, _pos_pattern in NEGATION_PATTERNS:
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
