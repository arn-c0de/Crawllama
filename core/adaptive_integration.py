"""
Integration module for Adaptive Hops functionality in CrawlLama API.

This module provides integration functions to add adaptive agent selection
to the existing CrawlLama API endpoints.

Author: CrawlLama Team
Version: 1.0.0
"""

from typing import Optional, Dict, Any, List, Tuple
import logging
import time
from core.adaptive_hops import AdaptiveHopManager, ComplexityLevel

logger = logging.getLogger(__name__)


class AdaptiveQueryProcessor:
    """
    Processes queries using adaptive agent selection.

    This class integrates the AdaptiveHopManager with the existing
    SearchAgent and MultiHopReasoningAgent to provide intelligent
    agent selection.
    """

    def __init__(
        self,
        agent,  # SearchAgent
        multihop_agent,  # MultiHopReasoningAgent
        adaptive_manager: AdaptiveHopManager,
        max_escalation_attempts: int = 2
    ):
        """
        Initialize the adaptive query processor.

        Args:
            agent: SearchAgent instance
            multihop_agent: MultiHopReasoningAgent instance
            adaptive_manager: AdaptiveHopManager instance
            max_escalation_attempts: Maximum escalation attempts
        """
        self.agent = agent
        self.multihop_agent = multihop_agent
        self.adaptive_manager = adaptive_manager
        # Clamp to at least one attempt; zero/negative would otherwise crash
        # the escalation loop before producing any result.
        self.max_escalation_attempts = max(1, max_escalation_attempts)

        logger.info("AdaptiveQueryProcessor initialized")

    def process_query(
        self,
        query: str,
        force_complexity: Optional[str] = None,
        enable_escalation: bool = True
    ) -> Dict[str, Any]:
        """
        Process a query using adaptive agent selection.

        Args:
            query: User query string
            force_complexity: Force specific complexity ("low", "mid", "high")
            enable_escalation: Enable confidence-based escalation

        Returns:
            Response dictionary with answer and metadata
        """
        start_time = time.time()

        # Phase 1: determine the initial strategy
        forced_complexity = self._parse_forced_complexity(force_complexity)
        strategy = self.adaptive_manager.decide_agent_strategy(
            query,
            force_complexity=forced_complexity
        )

        # Phase 2: execute, escalating to a stronger agent if needed
        result, strategy, attempt, escalation_history = self._run_with_escalation(
            query, strategy, enable_escalation
        )

        # Phase 3: assemble the final response
        response = self._build_response(result, strategy, attempt, escalation_history, start_time)

        logger.info(
            f"Query processed successfully | "
            f"Complexity: {strategy['complexity']} | "
            f"Agent: {strategy['agent_type']} | "
            f"Attempts: {attempt} | "
            f"Time: {response['metadata']['elapsed_time']:.2f}s"
        )

        return response

    @staticmethod
    def _parse_forced_complexity(force_complexity: Optional[str]) -> Optional[ComplexityLevel]:
        """Convert a force_complexity string to a ComplexityLevel, if valid."""
        if not force_complexity:
            return None

        try:
            return ComplexityLevel(force_complexity.lower())
        except ValueError:
            logger.warning("Invalid complexity level: %s", force_complexity)  # lgtm[py/log-injection] - parameterized logging; false positive
            return None

    def _run_with_escalation(
        self,
        query: str,
        strategy: Dict[str, Any],
        enable_escalation: bool
    ) -> Tuple[Dict[str, Any], Dict[str, Any], int, List[Dict[str, Any]]]:
        """Execute the query, escalating to a stronger agent on low confidence.

        Returns:
            Tuple of (result, final strategy, attempt count, escalation history)
        """
        attempt = 1
        escalation_history: List[Dict[str, Any]] = []

        while attempt <= self.max_escalation_attempts:
            logger.info(f"Processing query (attempt {attempt}) with strategy: {strategy['agent_type']}")

            result = self._execute_strategy(query, strategy)

            # Stop if escalation is disabled or max attempts reached
            if not enable_escalation or attempt >= self.max_escalation_attempts:
                break

            confidence = result.get("confidence")
            should_escalate, new_strategy = self.adaptive_manager.should_escalate(
                strategy,
                confidence=confidence,
                attempt_count=attempt
            )

            if not should_escalate:
                break

            escalation_history.append({
                "attempt": attempt,
                "from_agent": strategy["agent_type"],
                "to_agent": new_strategy["agent_type"],
                "reason": new_strategy.get("escalation_reason"),
                "confidence": confidence
            })
            strategy = new_strategy
            attempt += 1

        return result, strategy, attempt, escalation_history

    @staticmethod
    def _build_response(
        result: Dict[str, Any],
        strategy: Dict[str, Any],
        attempt: int,
        escalation_history: List[Dict[str, Any]],
        start_time: float
    ) -> Dict[str, Any]:
        """Assemble the final response dictionary from result and strategy."""
        response = {
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence"),
            "strategy": {
                "complexity": strategy["complexity"],
                "agent_type": strategy["agent_type"],
                "use_multihop": strategy["use_multihop"],
                "use_tools": strategy["use_tools"],
                "max_hops": strategy["max_hops"],
                "reasoning": strategy["reasoning"]
            },
            "metadata": {
                "complexity_analysis": strategy.get("complexity_metadata", {}),
                "resource_status": strategy.get("resource_status", {}),
                "attempts": attempt,
                "escalation_history": escalation_history,
                "elapsed_time": time.time() - start_time
            }
        }

        # Pass through optional fields from the agent result
        for key in ("steps", "search_queries", "reasoning_path"):
            if key in result:
                response[key] = result[key]

        return response

    def _execute_strategy(self, query: str, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute query based on selected strategy.

        Args:
            query: User query
            strategy: Strategy dictionary from AdaptiveHopManager

        Returns:
            Result dictionary
        """
        try:
            if strategy["use_multihop"]:
                # Use MultiHopReasoningAgent
                if not self.multihop_agent:
                    raise RuntimeError("MultiHopReasoningAgent not available")

                result = self.multihop_agent.query(query)

                return {
                    "answer": result.get("answer", ""),
                    "confidence": result.get("confidence"),
                    "steps": result.get("steps"),
                    "search_queries": result.get("search_queries"),
                    "reasoning_path": result.get("reasoning_path")
                }

            else:
                # Use SearchAgent
                if not self.agent:
                    raise RuntimeError("SearchAgent not available")

                answer = self.agent.query(query, use_tools=strategy["use_tools"])

                # SearchAgent doesn't return confidence, estimate based on answer quality
                confidence = self._estimate_confidence(answer)

                return {
                    "answer": answer,
                    "confidence": confidence
                }

        except Exception as e:
            logger.error(f"Strategy execution failed: {e}", exc_info=True)
            return {
                "answer": f"Error processing query: {str(e)}",
                "confidence": 0.0,
                "error": str(e)
            }

    def _estimate_confidence(self, answer: str) -> float:
        """
        Estimate confidence for SearchAgent responses.

        Args:
            answer: Answer string

        Returns:
            Confidence score (0-1)
        """
        # Simple heuristic-based confidence estimation
        if not answer or len(answer) < 10:
            return 0.3

        # Check for error indicators
        error_indicators = ["error", "failed", "not found", "unavailable", "sorry"]
        if any(indicator in answer.lower() for indicator in error_indicators):
            return 0.4

        # Check for uncertainty indicators
        uncertainty_indicators = ["might", "maybe", "possibly", "unclear", "unsure"]
        if any(indicator in answer.lower() for indicator in uncertainty_indicators):
            return 0.6

        # Default to reasonable confidence for normal answers
        answer_length = len(answer)
        if answer_length < 50:
            return 0.6
        elif answer_length < 200:
            return 0.75
        else:
            return 0.85

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about adaptive processing.

        Returns:
            Statistics dictionary
        """
        stats = {
            "adaptive_manager": self.adaptive_manager.get_stats(),
            "agents": {
                "search_agent": "available" if self.agent else "unavailable",
                "multihop_agent": "available" if self.multihop_agent else "unavailable"
            }
        }

        return stats


def initialize_adaptive_system(
    llm,
    agent,
    multihop_agent,
    system_monitor=None,
    performance_tracker=None
) -> tuple:
    """
    Initialize the adaptive hopping system.

    Args:
        llm: Language model instance
        agent: SearchAgent instance
        multihop_agent: MultiHopReasoningAgent instance
        system_monitor: Optional system monitor
        performance_tracker: Optional performance tracker

    Returns:
        Tuple of (adaptive_manager, query_processor)
    """
    from core.adaptive_hops import AdaptiveConfig

    # Create adaptive configuration
    config = AdaptiveConfig(
        enable_resource_monitoring=system_monitor is not None,
        enable_confidence_escalation=True,
        cpu_threshold_high=80.0,
        memory_threshold_high=85.0,
        max_hops_low=0,
        max_hops_mid=1,
        max_hops_high=5,
        fallback_on_resource_constraint=True,
        degraded_mode_max_hops=2
    )

    # Initialize adaptive manager
    adaptive_manager = AdaptiveHopManager(
        llm=llm,
        config=config,
        system_monitor=system_monitor,
        performance_tracker=performance_tracker
    )

    # Initialize query processor
    query_processor = AdaptiveQueryProcessor(
        agent=agent,
        multihop_agent=multihop_agent,
        adaptive_manager=adaptive_manager,
        max_escalation_attempts=2
    )

    logger.info("Adaptive system initialized successfully")
    return adaptive_manager, query_processor
