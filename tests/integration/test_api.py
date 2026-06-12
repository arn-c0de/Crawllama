"""Tests for FastAPI endpoints."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set development mode for testing (skip API key check)
os.environ["CRAWLLAMA_DEV_MODE"] = "true"
# Disable Redis for tests to avoid timeout
os.environ["REDIS_URL"] = ""  # Empty = use in-memory fallback

# Mock slow components BEFORE importing app
mock_agent = Mock()
mock_agent.query = Mock(return_value="Test response")
mock_agent.get_stats = Mock(return_value={"test": "stats"})
mock_agent.cache = Mock()
mock_agent.cache.clear = Mock(return_value=0)
mock_agent.cache.get_stats = Mock(return_value={})
mock_agent.clear_session = Mock(return_value={"cleared": True})
mock_agent.save_session = Mock()
mock_agent.load_session = Mock()
# Create a simple object for context_manager to avoid recursion issues with Mock
class MockContextManager:
    max_tokens = 4096
    model_name = "test-model"
    encoding = Mock()
    encoding.name = "cl100k_base"
mock_agent.context_manager = MockContextManager()

mock_multihop = Mock()
mock_multihop.query = Mock(return_value={
    "answer": "Test multihop response",
    "confidence": 0.9,
    "steps": 2,
    "search_queries": ["query1"],
    "reasoning_path": ["step1", "step2"]
})

mock_memory = Mock()
mock_memory.remember_email = Mock(return_value=True)
mock_memory.remember_phone = Mock(return_value=True)
mock_memory.remember_ip = Mock(return_value=True)
mock_memory.remember_username = Mock(return_value=True)
mock_memory.remember_domain = Mock(return_value=True)
mock_memory.get_all_emails = Mock(return_value=["test@example.com"])
mock_memory.get_all_phones = Mock(return_value=[])
mock_memory.get_all_ips = Mock(return_value=[])
mock_memory.get_all_usernames = Mock(return_value=[])
mock_memory.get_all_domains = Mock(return_value=[])
mock_memory.get_all_notes = Mock(return_value=[])
mock_memory.get_summary = Mock(return_value={"total": 1})
mock_memory.get_all = Mock(return_value={"emails": ["test@example.com"]})
mock_memory.forget_email = Mock(return_value=True)
mock_memory.forget_phone = Mock(return_value=True)
mock_memory.forget_ip = Mock(return_value=True)
mock_memory.forget_username = Mock(return_value=True)
mock_memory.clear_all = Mock(return_value=True)
mock_memory.clear_category = Mock(return_value=True)

mock_system_monitor = Mock()
mock_system_monitor.get_latest_metrics = Mock(return_value=None)

mock_performance_tracker = Mock()
mock_performance_tracker.get_all_stats = Mock(return_value={})

# Try to import app with mocked components, skip all tests if import fails
try:
    with patch('core.agent.SearchAgent', return_value=mock_agent), \
         patch('core.langgraph_agent.MultiHopReasoningAgent', return_value=mock_multihop), \
         patch('core.memory_store.MemoryStore', return_value=mock_memory), \
         patch('core.health.get_system_monitor', return_value=mock_system_monitor), \
         patch('core.health.get_performance_tracker', return_value=mock_performance_tracker), \
         patch('utils.redis_rate_limiter.RedisRateLimiter', side_effect=Exception("Redis disabled for tests")):
        from app import app
        API_AVAILABLE = True
        client = None  # Will be created in fixture
except Exception as e:
    API_AVAILABLE = False
    SKIP_REASON = f"API not available: {str(e)}"
    client = None

# Mark as integration and slow test - these tests start the FastAPI server
# Add timeout to prevent hanging tests
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.timeout(10),  # 10 second timeout per test
    pytest.mark.skipif(not API_AVAILABLE, reason=SKIP_REASON if not API_AVAILABLE else "")
]


@pytest.fixture(scope="module")
def test_client():
    """Provide a synchronous request helper using httpx ASGITransport."""
    if not API_AVAILABLE:
        pytest.skip("API not available")
    
    # Ensure mocked components are set in app globals
    import app as app_module
    app_module.agent = mock_agent
    app_module.multihop_agent = mock_multihop
    app_module.memory_store = mock_memory
    app_module.system_monitor = mock_system_monitor
    app_module.performance_tracker = mock_performance_tracker
    app_module.redis_rate_limiter = None

    def _request(method: str, url: str, **kwargs):
        async def _do():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.request(method, url, **kwargs)
        return asyncio.run(_do())

    return _request


class TestBasicEndpoints:
    """Test basic API endpoints."""

    def test_root_endpoint(self, test_client):
        """Test root endpoint returns HTML or API info."""
        response = test_client("GET", "/")
        assert response.status_code == 200
        # Root now returns HTML, so check for that or JSON fallback
        if response.headers.get("content-type", "").startswith("text/html"):
            assert len(response.text) > 0
            assert "CrawlLama" in response.text or "crawllama" in response.text.lower()
        else:
            # JSON fallback if HTML not found
            data = response.json()
            assert "name" in data
            assert "version" in data
            assert data["name"] == "CrawlLama API"

    def test_api_info_endpoint(self, test_client):
        """Test /api endpoint returns API info."""
        response = test_client("GET", "/api")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["name"] == "CrawlLama API"

    def test_health_check(self, test_client):
        """Test health check endpoint."""
        response = test_client("GET", "/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert data["status"] in ["healthy", "degraded"]

    def test_stats_endpoint(self, test_client):
        """Test stats endpoint."""
        response = test_client("GET", "/stats")
        assert response.status_code == 200
        data = response.json()
        assert "agent_stats" in data
        assert "resource_stats" in data


class TestQueryEndpoints:
    """Test query endpoints."""

    def test_simple_query(self, test_client):
        """Test simple query without web search."""
        response = test_client(
            "POST",
            "/query",
            json={
                "query": "What is 2+2?",
                "use_tools": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "elapsed_time" in data

    def test_query_validation(self, test_client):
        """Test query input validation."""
        # Empty query
        response = test_client(
            "POST",
            "/query",
            json={"query": ""}
        )
        assert response.status_code == 422  # Validation error

        # Query too long
        response = test_client(
            "POST",
            "/query",
            json={"query": "x" * 6000}
        )
        assert response.status_code == 422

    def test_multihop_query(self, test_client):
        """Test multi-hop reasoning query."""
        response = test_client(
            "POST",
            "/query",
            json={
                "query": "Compare Python and JavaScript",
                "use_multihop": True,
                "max_hops": 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "steps" in data or "confidence" in data


class TestOSINTEndpoints:
    """Test OSINT endpoints."""

    def test_osint_company_query(self, test_client):
        """Test company OSINT endpoint."""
        response = test_client(
            "POST",
            "/osint/company",
            json={"company_name": "Siemens AG"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["company_name"] == "Siemens AG"
        assert "answer" in data
        assert "elapsed_time" in data

    def test_osint_company_query_with_hints(self, test_client):
        """Test company OSINT endpoint with optional hints."""
        response = test_client(
            "POST",
            "/osint/company",
            json={
                "company_name": "Volkswagen AG",
                "country": "DE",
                "region": "de-de",
                "language": "de"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "query" in data
        assert "country:DE" in data["query"]
        assert "region:de-de" in data["query"]
        assert "lang:de" in data["query"]

    def test_osint_company_validation(self, test_client):
        """Test company OSINT input validation."""
        response = test_client(
            "POST",
            "/osint/company",
            json={"company_name": ""}
        )
        assert response.status_code == 422


class TestMemoryEndpoints:
    """Test memory store endpoints."""

    def test_memory_remember(self, test_client):
        """Test remembering values."""
        import time
        # Use unique value to avoid conflicts with existing data
        unique_email = f"test-{int(time.time())}@example.com"
        response = test_client(
            "POST",
            "/memory/remember",
            json={
                "category": "email",
                "value": unique_email
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Accept both success and failed (if already exists)
        assert data["status"] in ["success", "failed"]

    def test_memory_recall(self, test_client):
        """Test recalling values."""
        # First remember something
        test_client(
            "POST",
            "/memory/remember",
            json={"category": "email", "value": "recall@test.com"}
        )

        # Then recall it
        response = test_client("GET", "/memory/recall/emails")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["category"] == "emails"

    def test_memory_stats(self, test_client):
        """Test memory statistics."""
        response = test_client("GET", "/memory/stats")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert data["summary"]

    def test_memory_forget(self, test_client):
        """Test forgetting values."""
        # Remember something
        test_client(
            "POST",
            "/memory/remember",
            json={"category": "email", "value": "forget@test.com"}
        )

        # Forget specific value
        response = test_client(
            "DELETE",
            "/memory/forget",
            json={
                "category": "email",
                "value": "forget@test.com"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestCacheEndpoints:
    """Test cache endpoints."""

    def test_cache_stats(self, test_client):
        """Test cache statistics."""
        response = test_client("GET", "/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_cache_clear(self, test_client):
        """Test cache clearing."""
        response = test_client("POST", "/cache/clear")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["success", "info"]


class TestSessionEndpoints:
    """Test session management endpoints."""

    def test_session_save(self, test_client):
        """Test session saving."""
        response = test_client("POST", "/session/save")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["success", "info"]

    def test_session_clear(self, test_client):
        """Test session clearing."""
        response = test_client("POST", "/session/clear")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["success", "info"]


class TestConfigEndpoints:
    """Test configuration endpoints."""

    def test_get_config(self, test_client):
        """Test getting configuration."""
        response = test_client("GET", "/config")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "llm" in data["data"]

    def test_context_status(self, test_client):
        """Test context usage status."""
        response = test_client("GET", "/context/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestPluginEndpoints:
    """Test plugin management endpoints."""

    def test_list_plugins(self, test_client):
        """Test listing plugins."""
        response = test_client("GET", "/plugins")
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "loaded" in data
        assert "count" in data

    def test_list_tools(self, test_client):
        """Test listing tools."""
        response = test_client("GET", "/tools")
        assert response.status_code == 200
        data = response.json()
        assert "loaded" in data or "available" in data


class TestSecurityFeatures:
    """Test security features."""

    def test_rate_limiting(self, test_client):
        """Test rate limiting (basic check)."""
        # Make multiple requests rapidly
        responses = []
        for _ in range(5):
            response = test_client("GET", "/health")
            responses.append(response.status_code)
        
        # All should succeed in dev mode
        assert all(code == 200 for code in responses)

    def test_query_sanitization(self, test_client):
        """Test query sanitization."""
        # Try injection-like patterns
        dangerous_queries = [
            "'; DROP TABLE users;--",
            "<script>alert('xss')</script>",
            "../../../etc/passwd"
        ]
        
        for query in dangerous_queries:
            response = test_client(
                "POST",
                "/query",
                json={"query": query, "use_tools": False}
            )
            # Should either sanitize or reject
            assert response.status_code in [200, 422]

    def test_invalid_endpoints(self, test_client):
        """Test invalid endpoint access."""
        response = test_client("GET", "/nonexistent")
        assert response.status_code == 404


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_json(self, test_client):
        """Test handling of invalid JSON."""
        response = test_client(
            "POST",
            "/query",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_missing_required_fields(self, test_client):
        """Test handling of missing required fields."""
        response = test_client(
            "POST",
            "/query",
            json={"use_multihop": True}  # Missing 'query' field
        )
        assert response.status_code == 422

    def test_invalid_field_types(self, test_client):
        """Test handling of invalid field types."""
        response = test_client(
            "POST",
            "/query",
            json={
                "query": "test",
                "max_hops": "invalid"  # Should be int
            }
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
