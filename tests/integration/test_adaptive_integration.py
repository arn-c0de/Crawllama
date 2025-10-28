"""
Integration tests for Adaptive Agent Hopping System

Tests the integration between AdaptiveHopManager, AdaptiveQueryProcessor,
and the actual SearchAgent/MultiHopReasoningAgent.

Author: CrawlLama Team
Version: 1.0.0
"""

import pytest
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.adaptive_hops import AdaptiveHopManager, AdaptiveConfig, ComplexityLevel
from core.adaptive_integration import AdaptiveQueryProcessor, initialize_adaptive_system


class MockAgent:
    """Mock SearchAgent for testing."""

    def __init__(self, response="Test answer from SearchAgent"):
        self.response = response
        self.query_called_with = None
        self.use_tools = None

    def query(self, query, use_tools=True):
        self.query_called_with = query
        self.use_tools = use_tools
        return self.response


class MockMultihopAgent:
    """Mock MultiHopReasoningAgent for testing."""

    def __init__(self, response=None):
        self.response = response or {
            "answer": "Test answer from MultiHopAgent",
            "confidence": 0.85,
            "steps": 3,
            "search_queries": ["query1", "query2"],
            "reasoning_path": ["step1", "step2"]
        }
        self.query_called_with = None

    def query(self, query):
        self.query_called_with = query
        return self.response


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, complexity_response="MID"):
        self.complexity_response = complexity_response

    def generate(self, prompt, system_prompt=None):
        return self.complexity_response


class TestAdaptiveQueryProcessor:
    """Test AdaptiveQueryProcessor functionality."""

    def test_process_query_low_complexity(self):
        """Test processing LOW complexity query."""
        llm = MockLLM(complexity_response="LOW")
        agent = MockAgent()
        multihop_agent = MockMultihopAgent()
        manager = AdaptiveHopManager(llm=llm)

        processor = AdaptiveQueryProcessor(
            agent=agent,
            multihop_agent=multihop_agent,
            adaptive_manager=manager
        )

        result = processor.process_query("What is Python?")

        # Should use SearchAgent without tools
        assert agent.query_called_with == "What is Python?"
        assert agent.use_tools == False
        assert multihop_agent.query_called_with is None

        # Check result structure
        assert "answer" in result
        assert "strategy" in result
        assert result["strategy"]["complexity"] == "low"
        assert result["strategy"]["agent_type"] == "SearchAgent"

    def test_process_query_mid_complexity(self):
        """Test processing MID complexity query."""
        llm = MockLLM(complexity_response="MID")
        agent = MockAgent()
        multihop_agent = MockMultihopAgent()
        manager = AdaptiveHopManager(llm=llm)

        processor = AdaptiveQueryProcessor(
            agent=agent,
            multihop_agent=multihop_agent,
            adaptive_manager=manager
        )

        result = processor.process_query("Latest AI news")

        # Should use SearchAgent with tools
        assert agent.query_called_with == "Latest AI news"
        assert agent.use_tools == True
        assert multihop_agent.query_called_with is None

        assert result["strategy"]["complexity"] == "mid"
        assert result["strategy"]["use_tools"] == True

    def test_process_query_high_complexity(self):
        """Test processing HIGH complexity query."""
        llm = MockLLM(complexity_response="HIGH")
        agent = MockAgent()
        multihop_agent = MockMultihopAgent()
        manager = AdaptiveHopManager(llm=llm)

        processor = AdaptiveQueryProcessor(
            agent=agent,
            multihop_agent=multihop_agent,
            adaptive_manager=manager
        )

        result = processor.process_query("Compare X and Y, analyze trends")

        # Should use MultiHopAgent
        assert multihop_agent.query_called_with == "Compare X and Y, analyze trends"
        assert agent.query_called_with is None

        assert result["strategy"]["complexity"] == "high"
        assert result["strategy"]["use_multihop"] == True
        assert "steps" in result
        assert "reasoning_path" in result

    def test_process_query_with_force_complexity(self):
        """Test forcing specific complexity."""
        llm = MockLLM(complexity_response="LOW")  # LLM would say LOW
        agent = MockAgent()
        multihop_agent = MockMultihopAgent()
        manager = AdaptiveHopManager(llm=llm)

        processor = AdaptiveQueryProcessor(
            agent=agent,
            multihop_agent=multihop_agent,
            adaptive_manager=manager
        )

        # Force HIGH complexity
        result = processor.process_query(
            "Simple query",
            force_complexity="high"
        )

        # Should use MultiHopAgent despite simple query
        assert multihop_agent.query_called_with == "Simple query"
        assert result["strategy"]["complexity"] == "high"

    def test_escalation_on_low_confidence(self):
        """Test escalation when confidence is low."""
        llm = MockLLM(complexity_response="LOW")

        # First call returns low confidence
        agent = MockAgent("Short answer")

        # Second call should use multihop with better answer
        multihop_agent = MockMultihopAgent({
            "answer": "Detailed answer",
            "confidence": 0.9,
            "steps": 2,
            "search_queries": [],
            "reasoning_path": []
        })

        manager = AdaptiveHopManager(llm=llm)
        processor = AdaptiveQueryProcessor(
            agent=agent,
            multihop_agent=multihop_agent,
            adaptive_manager=manager
        )

        result = processor.process_query("Test query", enable_escalation=True)

        # Check escalation happened
        assert result["metadata"]["attempts"] >= 1

        # If escalated, should have escalation history
        if result["metadata"]["attempts"] > 1:
            assert len(result["metadata"]["escalation_history"]) > 0

    def test_escalation_disabled(self):
        """Test that escalation can be disabled."""
        llm = MockLLM(complexity_response="LOW")
        agent = MockAgent("Short answer")
        multihop_agent = MockMultihopAgent()
        manager = AdaptiveHopManager(llm=llm)

        processor = AdaptiveQueryProcessor(
            agent=agent,
            multihop_agent=multihop_agent,
            adaptive_manager=manager
        )

        result = processor.process_query("Test query", enable_escalation=False)

        # Should not escalate
        assert result["metadata"]["attempts"] == 1
        assert len(result["metadata"]["escalation_history"]) == 0

    def test_metadata_structure(self):
        """Test that metadata has correct structure."""
        llm = MockLLM(complexity_response="MID")
        agent = MockAgent()
        multihop_agent = MockMultihopAgent()
        manager = AdaptiveHopManager(llm=llm)

        processor = AdaptiveQueryProcessor(
            agent=agent,
            multihop_agent=multihop_agent,
            adaptive_manager=manager
        )

        result = processor.process_query("Test query")

        # Check metadata structure
        assert "metadata" in result
        metadata = result["metadata"]

        assert "complexity_analysis" in metadata
        assert "resource_status" in metadata
        assert "attempts" in metadata
        assert "escalation_history" in metadata
        assert "elapsed_time" in metadata
        assert isinstance(metadata["elapsed_time"], float)

    def test_confidence_estimation(self):
        """Test confidence estimation for SearchAgent responses."""
        llm = MockLLM(complexity_response="LOW")
        agent = MockAgent("Good detailed answer with sufficient information")
        multihop_agent = MockMultihopAgent()
        manager = AdaptiveHopManager(llm=llm)

        processor = AdaptiveQueryProcessor(
            agent=agent,
            multihop_agent=multihop_agent,
            adaptive_manager=manager
        )

        result = processor.process_query("Test query")

        # Should have estimated confidence
        assert "confidence" in result
        assert result["confidence"] is not None
        assert 0.0 <= result["confidence"] <= 1.0

    def test_error_in_agent_execution(self):
        """Test handling of agent execution errors."""

        class FailingAgent:
            def query(self, query, use_tools=True):
                raise Exception("Agent failed")

        llm = MockLLM(complexity_response="LOW")
        agent = FailingAgent()
        multihop_agent = MockMultihopAgent()
        manager = AdaptiveHopManager(llm=llm)

        processor = AdaptiveQueryProcessor(
            agent=agent,
            multihop_agent=multihop_agent,
            adaptive_manager=manager
        )

        result = processor.process_query("Test query")

        # Should return error message
        assert "Error processing query" in result["answer"]
        assert result["confidence"] == 0.0

    def test_get_processor_stats(self):
        """Test getting processor statistics."""
        llm = MockLLM()
        agent = MockAgent()
        multihop_agent = MockMultihopAgent()
        manager = AdaptiveHopManager(llm=llm)

        processor = AdaptiveQueryProcessor(
            agent=agent,
            multihop_agent=multihop_agent,
            adaptive_manager=manager
        )

        stats = processor.get_stats()

        assert "adaptive_manager" in stats
        assert "agents" in stats
        assert stats["agents"]["search_agent"] == "available"
        assert stats["agents"]["multihop_agent"] == "available"


class TestInitializeAdaptiveSystem:
    """Test initialize_adaptive_system function."""

    def test_initialize_without_monitors(self):
        """Test initialization without system monitors."""
        llm = MockLLM()
        agent = MockAgent()
        multihop_agent = MockMultihopAgent()

        adaptive_manager, query_processor = initialize_adaptive_system(
            llm=llm,
            agent=agent,
            multihop_agent=multihop_agent,
            system_monitor=None,
            performance_tracker=None
        )

        assert adaptive_manager is not None
        assert query_processor is not None
        assert isinstance(adaptive_manager, AdaptiveHopManager)
        assert isinstance(query_processor, AdaptiveQueryProcessor)

    def test_initialize_with_monitors(self):
        """Test initialization with system monitors."""

        class MockMonitor:
            def get_latest_metrics(self):
                class Metrics:
                    cpu_percent = 50.0
                    memory_percent = 60.0

                return Metrics()

        llm = MockLLM()
        agent = MockAgent()
        multihop_agent = MockMultihopAgent()
        monitor = MockMonitor()

        adaptive_manager, query_processor = initialize_adaptive_system(
            llm=llm,
            agent=agent,
            multihop_agent=multihop_agent,
            system_monitor=monitor,
            performance_tracker=None
        )

        # Should have monitoring enabled
        config = adaptive_manager.config
        assert config.enable_resource_monitoring == True

    def test_initialized_config_values(self):
        """Test that initialized system has correct config values."""
        llm = MockLLM()
        agent = MockAgent()
        multihop_agent = MockMultihopAgent()

        adaptive_manager, _ = initialize_adaptive_system(
            llm=llm,
            agent=agent,
            multihop_agent=multihop_agent
        )

        config = adaptive_manager.config

        # Check default values
        assert config.max_hops_low == 0
        assert config.max_hops_mid == 1
        assert config.max_hops_high == 5
        assert config.cpu_threshold_high == 80.0
        assert config.memory_threshold_high == 85.0


class TestEndToEndScenarios:
    """Test end-to-end scenarios."""

    def test_simple_question_flow(self):
        """Test complete flow for simple question."""
        llm = MockLLM(complexity_response="LOW")
        agent = MockAgent("Python is a programming language")
        multihop_agent = MockMultihopAgent()

        manager, processor = initialize_adaptive_system(
            llm=llm,
            agent=agent,
            multihop_agent=multihop_agent
        )

        result = processor.process_query("What is Python?")

        assert result["strategy"]["complexity"] == "low"
        assert "Python is a programming language" in result["answer"]
        assert result["metadata"]["attempts"] == 1

    def test_complex_analysis_flow(self):
        """Test complete flow for complex analysis."""
        llm = MockLLM(complexity_response="HIGH")
        agent = MockAgent()
        multihop_agent = MockMultihopAgent({
            "answer": "Detailed comparison: Healthcare shows 23% growth...",
            "confidence": 0.92,
            "steps": 4,
            "search_queries": ["healthcare AI", "manufacturing AI"],
            "reasoning_path": ["Initial search", "Comparison", "Analysis"]
        })

        manager, processor = initialize_adaptive_system(
            llm=llm,
            agent=agent,
            multihop_agent=multihop_agent
        )

        result = processor.process_query(
            "Compare AI in healthcare vs manufacturing"
        )

        assert result["strategy"]["complexity"] == "high"
        assert result["strategy"]["use_multihop"] == True
        assert result["confidence"] == 0.92
        assert result["steps"] == 4
        assert len(result["search_queries"]) == 2

    def test_resource_constrained_scenario(self):
        """Test scenario with resource constraints."""

        class ConstrainedMonitor:
            def get_latest_metrics(self):
                class Metrics:
                    cpu_percent = 90.0
                    memory_percent = 88.0

                return Metrics()

        llm = MockLLM(complexity_response="HIGH")
        agent = MockAgent()
        multihop_agent = MockMultihopAgent()
        monitor = ConstrainedMonitor()

        manager, processor = initialize_adaptive_system(
            llm=llm,
            agent=agent,
            multihop_agent=multihop_agent,
            system_monitor=monitor
        )

        result = processor.process_query("Complex query")

        # Under high resource usage, should degrade
        metadata = result["metadata"]
        assert metadata["resource_status"]["constrained"] == True

        # Strategy should reflect degradation
        strategy = result["strategy"]
        if strategy.get("degraded"):
            assert strategy["max_hops"] <= 2


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
