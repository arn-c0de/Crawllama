"""
Unit tests for Adaptive Agent Hopping System

Tests the core functionality of AdaptiveHopManager including:
- Query complexity analysis
- Resource constraint checking
- Strategy decision making
- Escalation logic

Author: CrawlLama Team
Version: 1.0.0
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.adaptive_hops import AdaptiveConfig, AdaptiveHopManager, ComplexityLevel


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, response="MID"):
        self.response = response
        self.call_count = 0

    def generate(self, prompt, system_prompt=None):
        self.call_count += 1
        return self.response


class MockSystemMonitor:
    """Mock system monitor for testing."""

    def __init__(self, cpu_percent=50.0, memory_percent=60.0):
        self.cpu_percent = cpu_percent
        self.memory_percent = memory_percent

    def get_latest_metrics(self):
        class Metrics:
            pass

        metrics = Metrics()
        metrics.cpu_percent = self.cpu_percent
        metrics.memory_percent = self.memory_percent
        return metrics


class TestComplexityAnalysis:
    """Test query complexity analysis."""

    def test_complexity_low_simple_query(self):
        """Test LOW complexity classification for simple queries."""
        llm = MockLLM(response="LOW")
        manager = AdaptiveHopManager(llm=llm)

        complexity, metadata = manager.analyze_query_complexity("What is Python?")

        assert complexity == ComplexityLevel.LOW
        assert metadata["query_length"] == 15
        assert "llm_classification" in metadata
        assert metadata["llm_classification"] == "LOW"

    def test_complexity_mid_medium_query(self):
        """Test MID complexity classification for medium queries."""
        llm = MockLLM(response="MID")
        manager = AdaptiveHopManager(llm=llm)

        query = "What are the latest developments in quantum computing?"
        complexity, metadata = manager.analyze_query_complexity(query)

        assert complexity == ComplexityLevel.MID
        assert metadata["query_length"] == len(query)

    def test_complexity_high_complex_query(self):
        """Test HIGH complexity classification for complex queries."""
        llm = MockLLM(response="HIGH")
        manager = AdaptiveHopManager(llm=llm)

        query = "Compare the economic impact of AI in healthcare versus manufacturing, then analyze which sector shows more growth potential over the next 5 years"
        complexity, metadata = manager.analyze_query_complexity(query)

        assert complexity == ComplexityLevel.HIGH
        assert metadata["query_length"] > 100
        assert "llm_classification" in metadata

    def test_complexity_multi_part_detection(self):
        """Test multi-part query detection."""
        llm = MockLLM(response="HIGH")
        manager = AdaptiveHopManager(llm=llm)

        query = "Compare X and Y, also analyze Z versus W"
        complexity, metadata = manager.analyze_query_complexity(query)

        # Should detect multi-part indicators
        factors = str(metadata.get("factors", []))
        assert "multi_part" in factors or complexity == ComplexityLevel.HIGH

    def test_complexity_temporal_detection(self):
        """Test temporal/sequential indicator detection."""
        llm = MockLLM(response="HIGH")
        manager = AdaptiveHopManager(llm=llm)

        query = "First analyze X, then compare with Y, finally recommend the best option"
        complexity, metadata = manager.analyze_query_complexity(query)

        # Should detect temporal indicators
        factors = str(metadata.get("factors", []))
        assert "temporal" in factors or complexity == ComplexityLevel.HIGH

    def test_complexity_fallback_on_llm_error(self):
        """Test fallback to heuristics when LLM fails."""
        class FailingLLM:
            def generate(self, prompt, system_prompt=None):
                raise Exception("LLM error")

        manager = AdaptiveHopManager(llm=FailingLLM())

        # Simple query - should fallback to LOW
        complexity, metadata = manager.analyze_query_complexity("Hi")
        assert metadata.get("fallback") == "heuristic"

        # Complex query - should fallback to HIGH
        complex_query = "Compare A and B, then analyze trends and recommend best option for the next 5 years"
        complexity, metadata = manager.analyze_query_complexity(complex_query)
        assert complexity in [ComplexityLevel.MID, ComplexityLevel.HIGH]
        assert metadata.get("fallback") == "heuristic"


class TestResourceConstraints:
    """Test resource constraint checking."""

    def test_no_constraints_normal_resources(self):
        """Test no constraints when resources are normal."""
        llm = MockLLM()
        monitor = MockSystemMonitor(cpu_percent=50.0, memory_percent=60.0)
        config = AdaptiveConfig(enable_resource_monitoring=True)

        manager = AdaptiveHopManager(llm=llm, config=config, system_monitor=monitor)
        status = manager.check_resource_constraints()

        assert not status["constrained"]
        assert status["cpu_percent"] == 50.0
        assert status["memory_percent"] == 60.0

    def test_constraints_high_cpu(self):
        """Test constraints when CPU is high."""
        llm = MockLLM()
        monitor = MockSystemMonitor(cpu_percent=85.0, memory_percent=60.0)
        config = AdaptiveConfig(
            enable_resource_monitoring=True,
            cpu_threshold_high=80.0
        )

        manager = AdaptiveHopManager(llm=llm, config=config, system_monitor=monitor)
        status = manager.check_resource_constraints()

        assert status["constrained"]
        assert "recommendation" in status

    def test_constraints_high_memory(self):
        """Test constraints when memory is high."""
        llm = MockLLM()
        monitor = MockSystemMonitor(cpu_percent=50.0, memory_percent=90.0)
        config = AdaptiveConfig(
            enable_resource_monitoring=True,
            memory_threshold_high=85.0
        )

        manager = AdaptiveHopManager(llm=llm, config=config, system_monitor=monitor)
        status = manager.check_resource_constraints()

        assert status["constrained"]

    def test_monitoring_disabled(self):
        """Test when resource monitoring is disabled."""
        llm = MockLLM()
        config = AdaptiveConfig(enable_resource_monitoring=False)

        manager = AdaptiveHopManager(llm=llm, config=config)
        status = manager.check_resource_constraints()

        assert not status["constrained"]
        assert status["reason"] == "monitoring_disabled"

    def test_no_monitor_provided(self):
        """Test when no system monitor is provided."""
        llm = MockLLM()
        config = AdaptiveConfig(enable_resource_monitoring=True)

        manager = AdaptiveHopManager(llm=llm, config=config, system_monitor=None)
        status = manager.check_resource_constraints()

        assert not status["constrained"]


class TestStrategyDecision:
    """Test agent strategy decision making."""

    def test_strategy_low_complexity(self):
        """Test strategy for LOW complexity queries."""
        llm = MockLLM(response="LOW")
        manager = AdaptiveHopManager(llm=llm)

        strategy = manager.decide_agent_strategy("What is Python?")

        assert strategy["complexity"] == "low"
        assert strategy["agent_type"] == "SearchAgent"
        assert not strategy["use_multihop"]
        assert not strategy["use_tools"]
        assert strategy["max_hops"] == 0

    def test_strategy_mid_complexity(self):
        """Test strategy for MID complexity queries."""
        llm = MockLLM(response="MID")
        manager = AdaptiveHopManager(llm=llm)

        strategy = manager.decide_agent_strategy("Latest AI news 2025")

        assert strategy["complexity"] == "mid"
        assert strategy["agent_type"] == "SearchAgent"
        assert not strategy["use_multihop"]
        assert strategy["use_tools"]
        assert strategy["max_hops"] == 1

    def test_strategy_high_complexity(self):
        """Test strategy for HIGH complexity queries."""
        llm = MockLLM(response="HIGH")
        manager = AdaptiveHopManager(llm=llm)

        strategy = manager.decide_agent_strategy("Compare X and Y, analyze trends")

        assert strategy["complexity"] == "high"
        assert strategy["agent_type"] == "MultiHopReasoningAgent"
        assert strategy["use_multihop"]
        assert strategy["use_tools"]
        assert strategy["max_hops"] == 5

    def test_strategy_with_resource_constraints(self):
        """Test strategy degradation under resource constraints."""
        llm = MockLLM(response="HIGH")
        monitor = MockSystemMonitor(cpu_percent=85.0, memory_percent=90.0)
        config = AdaptiveConfig(
            enable_resource_monitoring=True,
            fallback_on_resource_constraint=True,
            cpu_threshold_high=80.0,
            degraded_mode_max_hops=2
        )

        manager = AdaptiveHopManager(llm=llm, config=config, system_monitor=monitor)
        strategy = manager.decide_agent_strategy("Complex query requiring analysis")

        # Should be degraded from HIGH to MID or have reduced hops
        assert (strategy["complexity"] == "mid" or
                strategy["max_hops"] == 2 or
                strategy.get("degraded"))

    def test_force_complexity_override(self):
        """Test forcing specific complexity level."""
        llm = MockLLM(response="LOW")  # LLM would say LOW
        manager = AdaptiveHopManager(llm=llm)

        # Force HIGH complexity
        strategy = manager.decide_agent_strategy(
            "Simple query",
            force_complexity=ComplexityLevel.HIGH
        )

        assert strategy["complexity"] == "high"
        assert strategy["agent_type"] == "MultiHopReasoningAgent"

    def test_strategy_reasoning_populated(self):
        """Test that strategy includes reasoning."""
        llm = MockLLM(response="MID")
        manager = AdaptiveHopManager(llm=llm)

        strategy = manager.decide_agent_strategy("Test query")

        assert "reasoning" in strategy
        assert len(strategy["reasoning"]) > 0
        assert isinstance(strategy["reasoning"], list)


class TestEscalationLogic:
    """Test escalation logic."""

    def test_escalate_low_to_mid_on_low_confidence(self):
        """Test escalation from LOW to MID on low confidence."""
        llm = MockLLM()
        manager = AdaptiveHopManager(llm=llm)

        low_strategy = {
            "complexity": "low",
            "agent_type": "SearchAgent"
        }

        should_escalate, new_strategy = manager.should_escalate(
            low_strategy,
            confidence=0.4,
            attempt_count=1
        )

        assert should_escalate
        assert new_strategy["complexity"] == "mid"
        assert "escalation_reason" in new_strategy

    def test_escalate_mid_to_high_on_low_confidence(self):
        """Test escalation from MID to HIGH on low confidence."""
        llm = MockLLM()
        manager = AdaptiveHopManager(llm=llm)

        mid_strategy = {
            "complexity": "mid",
            "agent_type": "SearchAgent"
        }

        should_escalate, new_strategy = manager.should_escalate(
            mid_strategy,
            confidence=0.3,
            attempt_count=1
        )

        assert should_escalate
        assert new_strategy["complexity"] == "high"

    def test_no_escalation_high_confidence(self):
        """Test no escalation when confidence is high."""
        llm = MockLLM()
        manager = AdaptiveHopManager(llm=llm)

        low_strategy = {
            "complexity": "low",
            "agent_type": "SearchAgent"
        }

        should_escalate, new_strategy = manager.should_escalate(
            low_strategy,
            confidence=0.9,
            attempt_count=1
        )

        assert not should_escalate
        assert new_strategy is None

    def test_no_escalation_already_high(self):
        """Test no escalation when already at HIGH complexity."""
        llm = MockLLM()
        manager = AdaptiveHopManager(llm=llm)

        high_strategy = {
            "complexity": "high",
            "agent_type": "MultiHopReasoningAgent"
        }

        should_escalate, new_strategy = manager.should_escalate(
            high_strategy,
            confidence=0.4,
            attempt_count=1
        )

        assert not should_escalate

    def test_no_escalation_max_attempts(self):
        """Test no escalation when max attempts reached."""
        llm = MockLLM()
        manager = AdaptiveHopManager(llm=llm)

        low_strategy = {
            "complexity": "low",
            "agent_type": "SearchAgent"
        }

        should_escalate, new_strategy = manager.should_escalate(
            low_strategy,
            confidence=0.3,
            attempt_count=3  # More than max
        )

        assert not should_escalate

    def test_escalation_disabled(self):
        """Test escalation when disabled in config."""
        llm = MockLLM()
        config = AdaptiveConfig(enable_confidence_escalation=False)
        manager = AdaptiveHopManager(llm=llm, config=config)

        low_strategy = {
            "complexity": "low",
            "agent_type": "SearchAgent"
        }

        should_escalate, new_strategy = manager.should_escalate(
            low_strategy,
            confidence=0.3,
            attempt_count=1
        )

        assert not should_escalate


class TestAdaptiveConfig:
    """Test AdaptiveConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AdaptiveConfig()

        assert config.enable_resource_monitoring
        assert config.enable_confidence_escalation
        assert config.cpu_threshold_high == 80.0
        assert config.memory_threshold_high == 85.0
        assert config.confidence_low == 0.5
        assert config.max_hops_low == 0
        assert config.max_hops_mid == 1
        assert config.max_hops_high == 5

    def test_custom_config(self):
        """Test custom configuration."""
        config = AdaptiveConfig(
            cpu_threshold_high=70.0,
            max_hops_high=3,
            confidence_low=0.6
        )

        assert config.cpu_threshold_high == 70.0
        assert config.max_hops_high == 3
        assert config.confidence_low == 0.6


class TestStatistics:
    """Test statistics gathering."""

    def test_get_stats_basic(self):
        """Test basic stats retrieval."""
        llm = MockLLM()
        manager = AdaptiveHopManager(llm=llm)

        stats = manager.get_stats()

        assert "config" in stats
        assert "resource_monitoring" in stats["config"]
        assert "confidence_escalation" in stats["config"]
        assert "max_hops" in stats["config"]

    def test_get_stats_with_monitor(self):
        """Test stats with system monitor."""
        llm = MockLLM()
        monitor = MockSystemMonitor(cpu_percent=45.0, memory_percent=55.0)
        config = AdaptiveConfig(enable_resource_monitoring=True)

        manager = AdaptiveHopManager(llm=llm, config=config, system_monitor=monitor)
        stats = manager.get_stats()

        assert "current_resources" in stats
        assert stats["current_resources"]["cpu_percent"] == 45.0
        assert stats["current_resources"]["memory_percent"] == 55.0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_query(self):
        """Test handling of empty query."""
        llm = MockLLM(response="LOW")
        manager = AdaptiveHopManager(llm=llm)

        complexity, metadata = manager.analyze_query_complexity("")

        assert metadata["query_length"] == 0
        # Should still classify (likely as LOW)
        assert complexity in [ComplexityLevel.LOW, ComplexityLevel.MID, ComplexityLevel.HIGH]

    def test_very_long_query(self):
        """Test handling of very long query."""
        llm = MockLLM(response="HIGH")
        manager = AdaptiveHopManager(llm=llm)

        long_query = "A" * 1000
        complexity, metadata = manager.analyze_query_complexity(long_query)

        assert metadata["query_length"] == 1000
        # Long queries typically HIGH complexity
        assert complexity in [ComplexityLevel.HIGH, ComplexityLevel.MID]

    def test_none_confidence_escalation(self):
        """Test escalation with None confidence."""
        llm = MockLLM()
        manager = AdaptiveHopManager(llm=llm)

        strategy = {"complexity": "low", "agent_type": "SearchAgent"}

        should_escalate, new_strategy = manager.should_escalate(
            strategy,
            confidence=None,
            attempt_count=1
        )

        # Should not escalate if confidence is None
        assert not should_escalate


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
