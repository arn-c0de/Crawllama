"""Result dataclass for hallucination detection."""
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class HallucinationResult:
    """Result of hallucination detection analysis."""
    is_hallucination: bool
    confidence_score: float  # 0.0 - 1.0
    risk_level: str  # "low", "medium", "high"
    violations: list[dict[str, Any]]
    context_alignment: float  # How well response aligns with context
    fact_check_results: list[dict[str, Any]]
    quality_metrics: dict[str, float]
    processing_time: float
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
