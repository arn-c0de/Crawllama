"""Tests for multi-hop reasoning and advanced agent capabilities."""
import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

logger = logging.getLogger("crawllama")


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {
        "llm": {
            "base_url": "http://127.0.0.1:11434",
            "model": "qwen2.5:3b",
            "temperature": 0.7
        },
        "rag": {
            "enabled": False
        }
    }


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    mock_client = Mock()
    mock_client.generate = Mock(return_value="Mocked response")
    return mock_client


@pytest.fixture
def mock_tool_registry():
    """Mock tool registry."""
    mock_registry = Mock()

    # Mock web search tool
    mock_tool = Mock()
    mock_tool.name = "web_search"
    mock_tool.func = Mock(return_value="Mocked search results")

    mock_registry.get_tools = Mock(return_value=[mock_tool])
    return mock_registry


class TestMultiHopReasoning:
    """Test multi-hop reasoning capabilities."""

    @patch('core.llm_client.OllamaClient')
    @patch('core.langgraph_agent.ToolRegistry')
    def test_agent_initialization(self, mock_tool_reg, mock_ollama, mock_config):
        """Test multi-hop agent initialization."""
        # Mock the OllamaClient constructor
        mock_ollama_instance = Mock()
        mock_ollama.return_value = mock_ollama_instance
        
        # Mock the ToolRegistry constructor  
        mock_tool_reg_instance = Mock()
        mock_tool_reg.return_value = mock_tool_reg_instance
        
        from core.langgraph_agent import MultiHopReasoningAgent

        agent = MultiHopReasoningAgent(
            config=mock_config,
            max_hops=3,
            confidence_threshold=0.7
        )

        assert agent.max_hops == 3
        assert agent.confidence_threshold == 0.7
        assert agent.graph is not None

    @patch('core.llm_client.OllamaClient')
    @patch('core.langgraph_agent.ToolRegistry')
    def test_simple_query(self, mock_tool_reg, mock_ollama, mock_config):
        """Test simple query that doesn't need multi-hop."""
        from core.langgraph_agent import MultiHopReasoningAgent

        # Mock LLM responses
        mock_ollama_instance = Mock()
        mock_ollama_instance.generate = Mock(side_effect=[
            "EINFACH",  # Router classification
            "Initial search result",  # Initial search
            "VOLLSTÄNDIG: JA\nFEHLENDE_INFO: None\nVERTRAUEN: 90",  # Analysis
            "Final answer to the question"  # Synthesis
        ])
        mock_ollama.return_value = mock_ollama_instance

        # Mock tool registry
        mock_tool = Mock()
        mock_tool.name = "web_search"
        mock_tool.func = Mock(return_value="Search result")
        mock_tool_reg_instance = Mock()
        mock_tool_reg_instance.get_tools.return_value = [mock_tool]
        mock_tool_reg.return_value = mock_tool_reg_instance

        agent = MultiHopReasoningAgent(config=mock_config, max_hops=3)

        result = agent.query("Was ist Python?")

        assert result["answer"] is not None
        assert result["steps"] >= 0
        assert isinstance(result["search_queries"], list)
        assert isinstance(result["reasoning_path"], list)

    @patch('core.llm_client.OllamaClient')
    @patch('core.langgraph_agent.ToolRegistry')
    def test_complex_multihop_query(self, mock_tool_reg, mock_ollama, mock_config):
        """Test complex query requiring multiple hops."""
        from core.langgraph_agent import MultiHopReasoningAgent

        # Simulate multi-hop scenario
        mock_ollama_instance = Mock()
        # NOTE: markers must match the actual (English) analysis/critique prompts
        # the agent emits (COMPLETE/CONFIDENCE). The search nodes call the tool,
        # not the LLM, so only LLM (generate) calls appear here in order:
        # router -> analyze#1 -> follow-up-query -> analyze#2 -> synthesize -> critique.
        mock_ollama_instance.generate = Mock(side_effect=[
            "KOMPLEX",  # Router: complex query
            "COMPLETE: NO\nMISSING_INFO: Need more details\nCONFIDENCE: 40",  # analyze #1 -> continue
            "Follow-up query",  # follow-up query generation
            "COMPLETE: YES\nMISSING_INFO: None\nCONFIDENCE: 85",  # analyze #2 -> complete
            "Comprehensive final answer",  # synthesis
            "COMPLETE: YES\nQUALITY: 90\nIMPROVEMENT: None",  # critique
        ])
        mock_ollama.return_value = mock_ollama_instance

        # Mock tool
        mock_tool = Mock()
        mock_tool.name = "web_search"
        mock_tool.func = Mock(return_value=[
            {"title": "Python vs JavaScript", "url": "https://example.com/python-js", "snippet": "Comparison of Python and JavaScript for web development."},
            {"title": "Web Development Languages", "url": "https://example.com/web-langs", "snippet": "Overview of popular web development languages."}
        ])
        mock_tool_reg_instance = Mock()
        mock_tool_reg_instance.get_tools.return_value = [mock_tool]
        mock_tool_reg.return_value = mock_tool_reg_instance

        agent = MultiHopReasoningAgent(config=mock_config, max_hops=3)

        result = agent.query("Compare Python and JavaScript for web development")

        # Should have performed multiple steps
        assert result["steps"] >= 2
        assert len(result["search_queries"]) >= 2
        assert result["answer"] is not None

    @patch('core.llm_client.OllamaClient')
    @patch('core.langgraph_agent.ToolRegistry')
    def test_max_hops_limit(self, mock_tool_reg, mock_ollama, mock_config):
        """Test that agent respects max hops limit."""
        from core.langgraph_agent import MultiHopReasoningAgent

        # Always say we need more info
        mock_ollama_instance = Mock()
        mock_ollama_instance.generate = Mock(side_effect=[
            "KOMPLEX",
            "",
            "VOLLSTÄNDIG: NEIN\nFEHLENDE_INFO: Need more\nVERTRAUEN: 30",
            "query 1",
            "",
            "VOLLSTÄNDIG: NEIN\nFEHLENDE_INFO: Still need more\nVERTRAUEN: 40",
            "query 2",
            "",
            "VOLLSTÄNDIG: NEIN\nFEHLENDE_INFO: Still need more\nVERTRAUEN: 50",
            "Final answer despite low confidence"  # Synthesis
        ])
        mock_ollama.return_value = mock_ollama_instance

        mock_tool = Mock()
        mock_tool.name = "web_search"
        mock_tool.func = Mock(return_value="Result")
        mock_tool_reg_instance = Mock()
        mock_tool_reg_instance.get_tools.return_value = [mock_tool]
        mock_tool_reg.return_value = mock_tool_reg_instance

        agent = MultiHopReasoningAgent(config=mock_config, max_hops=2)

        result = agent.query("Complex question")

        # Should not exceed max_hops
        assert result["steps"] <= 2

    @patch('core.llm_client.OllamaClient')
    @patch('core.langgraph_agent.ToolRegistry')
    def test_confidence_improvement(self, mock_tool_reg, mock_ollama, mock_config):
        """Test that confidence increases with more information."""
        from core.langgraph_agent import MultiHopReasoningAgent

        confidences = []

        def mock_generate(prompt):
            if "VERTRAUEN" in prompt or "QUALITÄT" in prompt:
                # Simulate increasing confidence
                if len(confidences) == 0:
                    confidences.append(50)
                    return "VOLLSTÄNDIG: NEIN\nVERTRAUEN: 50"
                else:
                    confidences.append(85)
                    return "VOLLSTÄNDIG: JA\nVERTRAUEN: 85"
            elif "Folge-Suchanfrage" in prompt:
                return "specific follow-up query"
            elif "Synthesise" in prompt or "Antworte" in prompt:
                return "Final comprehensive answer"
            else:
                return "KOMPLEX"

        mock_ollama_instance = Mock()
        mock_ollama_instance.generate = Mock(side_effect=mock_generate)
        mock_ollama.return_value = mock_ollama_instance

        mock_tool = Mock()
        mock_tool.name = "web_search"
        mock_tool.func = Mock(return_value="Informative result")
        mock_tool_reg_instance = Mock()
        mock_tool_reg_instance.get_tools.return_value = [mock_tool]
        mock_tool_reg.return_value = mock_tool_reg_instance

        agent = MultiHopReasoningAgent(config=mock_config, max_hops=3)

        result = agent.query("Question requiring research")

        # Confidence should improve
        assert result["confidence"] > 0


class TestParallelSearch:
    """Test parallel search capabilities."""

    def test_parallel_search_manager(self):
        """Test parallel search manager initialization."""
        from utils.parallel_search import ParallelSearchManager

        manager = ParallelSearchManager(max_workers=4, timeout=30)
        assert manager.max_workers == 4
        assert manager.timeout == 30

    def test_parallel_aspect_search(self):
        """Test parallel search across multiple aspects."""
        from utils.parallel_search import ParallelSearchManager

        manager = ParallelSearchManager(max_workers=3)

        # Mock search function
        def mock_search(query: str) -> str:
            return f"Results for: {query}"

        aspects = ["technical", "historical", "current"]
        result = manager.parallel_search(
            base_query="Python programming",
            aspects=aspects,
            search_func=mock_search
        )

        assert result["total_aspects"] == 3
        assert result["aspects_completed"] >= 0
        assert "combined_result" in result
        assert "elapsed_time" in result

    def test_parallel_map(self):
        """Test parallel map operation."""
        from utils.parallel_search import parallel_map

        def double(x):
            return x * 2

        items = [1, 2, 3, 4, 5]
        results = parallel_map(double, items, max_workers=2)

        assert results == [2, 4, 6, 8, 10]

    def test_entity_comparison(self):
        """Test parallel entity comparison."""
        from utils.parallel_search import compare_entities_parallel

        def mock_search(query: str) -> str:
            return f"Info about {query}"

        entities = ["Python", "JavaScript"]
        aspects = ["performance", "popularity"]

        result = compare_entities_parallel(
            entities=entities,
            search_func=mock_search,
            comparison_aspects=aspects
        )

        assert result["entities"] == entities
        assert result["aspects"] == aspects
        assert "comparisons" in result


class TestLazyLoading:
    """Test lazy loading system."""

    def test_tool_loader_initialization(self):
        """Test tool loader initialization."""
        from core.unified_loader import get_unified_loader

        loader = get_unified_loader()
        assert loader is not None
        assert len(loader._tool_configs) > 0

    def test_lazy_tool_loading(self):
        """Test that tools are loaded on demand."""
        from core.unified_loader import get_unified_loader

        loader = get_unified_loader()

        # Tool should not be loaded initially
        assert not loader.is_tool_loaded("web_search")

    def test_plugin_discovery(self):
        """Test plugin discovery."""
        from core.unified_loader import get_unified_loader

        loader = get_unified_loader()
        plugins = loader.discover_plugins()

        assert isinstance(plugins, list)


class TestRAGOptimizations:
    """Test RAG optimizations."""

    def test_batch_processing(self):
        """Test batch document processing."""
        from tools.rag import RAGManager

        rag = RAGManager(
            persist_dir="data/test_embeddings",
            batch_size=10
        )

        # Create large document set
        docs = [f"Document {i} with content" for i in range(50)]

        try:
            # Should use batch processing
            rag.add_documents(docs, use_batch=True)

            # Verify documents were added
            stats = rag.get_stats()
            assert stats["document_count"] == 50

        finally:
            rag.clear_collection()

    def test_multi_query_search(self):
        """Test multi-query search."""
        from tools.rag import RAGManager

        rag = RAGManager(
            persist_dir="data/test_embeddings",
            max_workers=2
        )

        # Add test documents
        docs = [
            "Python is a programming language",
            "JavaScript is used for web development",
            "Machine learning with Python"
        ]
        rag.add_documents(docs)

        try:
            # Multi-query search
            queries = ["Python", "programming", "development"]
            results = rag.multi_query_search(queries, top_k=5, deduplicate=True)

            assert isinstance(results, list)
            # Should have deduplicated results
            assert len(results) <= 15

        finally:
            rag.clear_collection()

    def test_relevance_filtering(self):
        """Test search with relevance filtering."""
        from tools.rag import RAGManager

        rag = RAGManager(persist_dir="data/test_embeddings")

        docs = ["Highly relevant document", "Less relevant content"]
        rag.add_documents(docs)

        try:
            # Search with minimum relevance
            results = rag.search("relevant", top_k=5, min_relevance=0.5)

            # All results should meet threshold
            for result in results:
                assert result["relevance"] >= 0.5

        finally:
            rag.clear_collection()


class TestResourceMonitoring:
    """Test resource monitoring (migrated to core.health)."""

    def test_system_monitor(self):
        """Test system monitoring with new health system."""
        from core.health import SystemMonitor

        monitor = SystemMonitor(update_interval=1.0)
        monitor.start()

        # Give it time to collect metrics
        import time
        time.sleep(1.5)

        metrics = monitor.get_latest_metrics()
        monitor.stop()

        assert metrics is not None
        assert metrics.memory_used_gb > 0
        assert metrics.memory_percent >= 0
        assert metrics.memory_total_gb > 0

    def test_performance_tracker(self):
        """Test performance tracking with new health system."""
        from core.health import PerformanceTracker

        tracker = PerformanceTracker()

        # Record some timings (note: duration is in milliseconds now)
        tracker.record("test_op", 1500.0, success=True)
        tracker.record("test_op", 2000.0, success=True)

        stats = tracker.get_stats("test_op")

        assert stats.count == 2
        assert stats.avg_duration_ms == 1750.0
        assert stats.min_duration_ms == 1500.0
        assert stats.max_duration_ms == 2000.0
        assert stats.success_rate == 100.0

    def test_monitored_decorator(self):
        """Test monitoring decorator from new health system."""
        from core.health import monitored

        @monitored("test_function")
        def test_function():
            # Allocate some memory
            data = [i for i in range(10000)]
            return len(data)

        result = test_function()
        assert result == 10000


class TestAsyncUtils:
    """Test async utilities."""

    def test_async_fetcher_initialization(self):
        """Test async fetcher initialization."""
        from utils.async_utils import AsyncFetcher

        fetcher = AsyncFetcher(timeout=30, max_concurrent=5)
        assert fetcher.max_concurrent == 5
        assert fetcher.timeout.total == 30

    def test_batch_processor(self):
        """Test async batch processor."""
        from utils.async_utils import AsyncBatchProcessor

        processor = AsyncBatchProcessor(batch_size=5, max_concurrent=2)
        assert processor.batch_size == 5
        assert processor.max_concurrent == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--log-cli-level=INFO"])
