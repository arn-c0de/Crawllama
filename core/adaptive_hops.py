"""
Adaptive Agent Hopping System for CrawlLama

This module provides intelligent agent selection based on query complexity,
system resources, and performance metrics. It automatically routes queries
to the most appropriate agent (SearchAgent or MultiHopReasoningAgent) with
optimal configuration.

Author: CrawlLama Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ComplexityLevel(Enum):
    """Query complexity levels for agent selection."""
    LOW = "low"      # Simple, factual queries - use SearchAgent without tools
    MID = "mid"      # Medium queries requiring web search - use SearchAgent with tools
    HIGH = "high"    # Complex, multi-step queries - use MultiHopReasoningAgent


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive agent hopping."""
    # Complexity thresholds
    enable_resource_monitoring: bool = True
    enable_confidence_escalation: bool = True

    # Resource thresholds (%)
    cpu_threshold_high: float = 80.0
    memory_threshold_high: float = 85.0

    # Confidence thresholds
    confidence_low: float = 0.5
    confidence_medium: float = 0.7
    confidence_high: float = 0.85

    # Max hops configuration per complexity
    max_hops_low: int = 0
    max_hops_mid: int = 1
    max_hops_high: int = 5

    # Fallback behavior
    fallback_on_resource_constraint: bool = True
    degraded_mode_max_hops: int = 2


class AdaptiveHopManager:
    """
    Manages adaptive agent selection based on query complexity and system state.

    This class analyzes incoming queries and determines the optimal agent and
    configuration to use, considering:
    - Query complexity (Low/Mid/High)
    - System resources (CPU, memory)
    - Historical performance
    - Confidence requirements
    """

    def __init__(
        self,
        llm: Any,
        config: AdaptiveConfig | None = None,
        system_monitor: Any | None = None,
        performance_tracker: Any | None = None
    ):
        """
        Initialize the adaptive hop manager.

        Args:
            llm: Language model for complexity analysis
            config: Adaptive configuration settings
            system_monitor: System resource monitor (optional)
            performance_tracker: Performance tracking system (optional)
        """
        self.llm = llm
        self.config = config or AdaptiveConfig()
        self.system_monitor = system_monitor
        self.performance_tracker = performance_tracker

        logger.info("AdaptiveHopManager initialized")

    def analyze_query_complexity(self, query: str) -> tuple[ComplexityLevel, dict[str, Any]]:
        """
        Analyze query complexity using multi-factor analysis.

        Args:
            query: User query string

        Returns:
            Tuple of (complexity_level, analysis_metadata)
        """
        metadata = {
            "query_length": len(query),
            "factors": []
        }

        # Factor 1: Query length heuristic
        query_length = len(query)
        if query_length < 50:
            length_score = "simple"
        elif query_length < 150:
            length_score = "medium"
        else:
            length_score = "complex"
        metadata["factors"].append(f"length: {length_score}")

        # Factor 2: Multi-part question detection
        multi_part_indicators = ["and", "also", "additionally", "compare", "versus", "vs"]
        has_multi_parts = any(indicator in query.lower() for indicator in multi_part_indicators)
        if has_multi_parts:
            metadata["factors"].append("multi_part: yes")

        # Factor 3: Temporal/sequential indicators
        temporal_indicators = ["after", "before", "then", "first", "next", "finally", "steps"]
        has_temporal = any(indicator in query.lower() for indicator in temporal_indicators)
        if has_temporal:
            metadata["factors"].append("temporal: yes")

        # Factor 4: LLM-based complexity analysis
        complexity_prompt = f"""Analyze this query and classify its complexity:

Query: "{query}"

Classification criteria:
- LOW: Simple factual question, single-step answer (e.g., "What is the capital of France?")
- MID: Requires web search or specific information (e.g., "Latest news about AI")
- HIGH: Multi-step reasoning, comparisons, or complex analysis (e.g., "Compare the economic impact of X and Y, then analyze trends")

Respond ONLY with: LOW, MID, or HIGH"""

        try:
            llm_decision = self.llm.generate(
                prompt=complexity_prompt,
                system_prompt="You are a query complexity classifier."
            ).strip().upper()

            metadata["llm_classification"] = llm_decision

            # Map LLM decision to complexity level
            if "LOW" in llm_decision:
                complexity = ComplexityLevel.LOW
            elif "HIGH" in llm_decision:
                complexity = ComplexityLevel.HIGH
            else:
                complexity = ComplexityLevel.MID

        except Exception as e:
            logger.warning(f"LLM complexity analysis failed: {e}")
            # Fallback to heuristic-based classification
            if has_temporal or has_multi_parts or query_length > 150:
                complexity = ComplexityLevel.HIGH
            elif query_length > 50 or has_multi_parts:
                complexity = ComplexityLevel.MID
            else:
                complexity = ComplexityLevel.LOW

            metadata["fallback"] = "heuristic"

        logger.info(f"Query complexity: {complexity.value} | Factors: {metadata['factors']}")
        return complexity, metadata

    def check_resource_constraints(self) -> dict[str, Any]:
        """
        Check system resource constraints.

        Returns:
            Dictionary with resource status and recommendations
        """
        if not self.config.enable_resource_monitoring or not self.system_monitor:
            return {
                "constrained": False,
                "reason": "monitoring_disabled"
            }

        try:
            metrics = self.system_monitor.get_latest_metrics()
            if not metrics:
                return {"constrained": False, "reason": "no_metrics"}

            cpu_high = metrics.cpu_percent > self.config.cpu_threshold_high
            memory_high = metrics.memory_percent > self.config.memory_threshold_high

            if cpu_high or memory_high:
                return {
                    "constrained": True,
                    "cpu_percent": metrics.cpu_percent,
                    "memory_percent": metrics.memory_percent,
                    "recommendation": "use_lighter_agent"
                }

            return {
                "constrained": False,
                "cpu_percent": metrics.cpu_percent,
                "memory_percent": metrics.memory_percent
            }

        except Exception as e:
            logger.warning(f"Resource check failed: {e}")
            return {"constrained": False, "reason": "check_failed"}

    def decide_agent_strategy(
        self,
        query: str,
        force_complexity: ComplexityLevel | None = None
    ) -> dict[str, Any]:
        """
        Decide optimal agent strategy based on all factors.

        Args:
            query: User query
            force_complexity: Override complexity detection (optional)

        Returns:
            Strategy dictionary with agent selection and configuration
        """
        # Step 1: Analyze query complexity
        if force_complexity:
            complexity = force_complexity
            complexity_metadata = {"forced": True}
        else:
            complexity, complexity_metadata = self.analyze_query_complexity(query)

        # Step 2: Check resource constraints
        resource_status = self.check_resource_constraints()

        # Step 3: Determine agent and configuration
        strategy = {
            "complexity": complexity.value,
            "complexity_metadata": complexity_metadata,
            "resource_status": resource_status,
            "agent_type": None,
            "use_multihop": False,
            "use_tools": True,
            "max_hops": 3,
            "confidence_threshold": 0.7,
            "reasoning": []
        }

        # Apply resource-based degradation if needed
        resource_constrained = resource_status.get("constrained", False)
        if resource_constrained and self.config.fallback_on_resource_constraint:
            strategy["reasoning"].append("Resource constrained - downgrading complexity")
            if complexity == ComplexityLevel.HIGH:
                complexity = ComplexityLevel.MID
                strategy["degraded"] = True

        # Select agent based on complexity
        if complexity == ComplexityLevel.LOW:
            # Low complexity: SearchAgent, minimal tools
            strategy["agent_type"] = "SearchAgent"
            strategy["use_multihop"] = False
            strategy["use_tools"] = False  # Context-only mode
            strategy["max_hops"] = self.config.max_hops_low
            strategy["reasoning"].append("Low complexity: SearchAgent without tools")

        elif complexity == ComplexityLevel.MID:
            # Mid complexity: SearchAgent with tools
            strategy["agent_type"] = "SearchAgent"
            strategy["use_multihop"] = False
            strategy["use_tools"] = True
            strategy["max_hops"] = self.config.max_hops_mid
            strategy["reasoning"].append("Mid complexity: SearchAgent with web tools")

        else:  # ComplexityLevel.HIGH
            # High complexity: MultiHopReasoningAgent
            strategy["agent_type"] = "MultiHopReasoningAgent"
            strategy["use_multihop"] = True
            strategy["use_tools"] = True

            # Adjust max_hops based on resources
            if resource_constrained:
                strategy["max_hops"] = self.config.degraded_mode_max_hops
                strategy["reasoning"].append(f"High complexity with resource constraints: {strategy['max_hops']} hops")
            else:
                strategy["max_hops"] = self.config.max_hops_high
                strategy["reasoning"].append(f"High complexity: MultiHop with {strategy['max_hops']} hops")

        logger.info(f"Agent strategy: {strategy['agent_type']} | Reasoning: {' | '.join(strategy['reasoning'])}")
        return strategy

    def should_escalate(
        self,
        current_strategy: dict[str, Any],
        confidence: float | None = None,
        attempt_count: int = 1
    ) -> tuple[bool, dict[str, Any] | None]:
        """
        Determine if query should be escalated to more complex agent.

        Args:
            current_strategy: Current agent strategy
            confidence: Confidence score from previous attempt (0-1)
            attempt_count: Number of attempts made

        Returns:
            Tuple of (should_escalate, new_strategy)
        """
        if not self.config.enable_confidence_escalation:
            return False, None

        # Don't escalate if already at highest complexity
        if current_strategy["agent_type"] == "MultiHopReasoningAgent":
            logger.info("Already at highest complexity - no escalation")
            return False, None

        # Don't escalate if too many attempts
        if attempt_count > 2:
            logger.info("Max escalation attempts reached")
            return False, None

        # Escalate if confidence is too low
        should_escalate = False
        reason = None

        if confidence is not None and confidence < self.config.confidence_low:
            should_escalate = True
            reason = f"Low confidence ({confidence:.2f})"

        if not should_escalate:
            return False, None

        # Determine new complexity level
        current_complexity = ComplexityLevel(current_strategy["complexity"])
        if current_complexity == ComplexityLevel.LOW:
            new_complexity = ComplexityLevel.MID
        else:
            new_complexity = ComplexityLevel.HIGH

        logger.info(f"Escalating: {reason} | {current_complexity.value} -> {new_complexity.value}")

        # Generate new strategy - use empty query since we're forcing complexity
        new_strategy = self.decide_agent_strategy("", force_complexity=new_complexity)
        new_strategy["escalation_reason"] = reason
        new_strategy["attempt"] = attempt_count + 1

        return True, new_strategy

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about agent selection decisions.

        Returns:
            Statistics dictionary
        """
        stats = {
            "config": {
                "resource_monitoring": self.config.enable_resource_monitoring,
                "confidence_escalation": self.config.enable_confidence_escalation,
                "max_hops": {
                    "low": self.config.max_hops_low,
                    "mid": self.config.max_hops_mid,
                    "high": self.config.max_hops_high
                }
            }
        }

        if self.system_monitor:
            try:
                metrics = self.system_monitor.get_latest_metrics()
                if metrics:
                    stats["current_resources"] = {
                        "cpu_percent": metrics.cpu_percent,
                        "memory_percent": metrics.memory_percent
                    }
            except Exception as e:
                logger.warning(f"Failed to get resource stats: {e}")

        return stats
