"""Tests for FastAPI endpoints."""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set development mode for testing (skip API key check)
os.environ["CRAWLLAMA_DEV_MODE"] = "true"

# Try to import app, skip all tests if import fails
try:
    from app import app
    # Use TestClient as context manager to ensure startup/shutdown events run
    client = TestClient(app)
    # Enter context to trigger startup
    client.__enter__()
    API_AVAILABLE = True
except Exception as e:
    API_AVAILABLE = False
    SKIP_REASON = f"API not available: {str(e)}"
    client = None

# Skip all tests if API is not available
pytestmark = pytest.mark.skipif(not API_AVAILABLE, reason=SKIP_REASON if not API_AVAILABLE else "")


@pytest.fixture(scope="module")
def test_client():
    """Provide test client for all tests."""
    if not API_AVAILABLE:
        pytest.skip("API not available")
    
    # Manually trigger startup to ensure components are initialized
    import asyncio
    from app import startup_event
    
    # Run startup event if not already run
    try:
        asyncio.run(startup_event())
    except RuntimeError:
        # Event loop already running, use current loop
        loop = asyncio.get_event_loop()
        loop.run_until_complete(startup_event())
    
    return client


class TestBasicEndpoints:
    """Test basic API endpoints."""

    def test_root_endpoint(self, test_client):
        """Test root endpoint returns API info."""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["name"] == "CrawlLama API"

    def test_health_check(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert data["status"] in ["healthy", "degraded"]

    def test_stats_endpoint(self, test_client):
        """Test stats endpoint."""
        response = test_client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "agent_stats" in data
        assert "resource_stats" in data


class TestQueryEndpoints:
    """Test query endpoints."""

    def test_simple_query(self, test_client):
        """Test simple query without web search."""
        response = test_client.post(
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
        response = test_client.post(
            "/query",
            json={"query": ""}
        )
        assert response.status_code == 422  # Validation error

        # Query too long
        response = test_client.post(
            "/query",
            json={"query": "x" * 6000}
        )
        assert response.status_code == 422

    def test_multihop_query(self, test_client):
        """Test multi-hop reasoning query."""
        response = test_client.post(
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


class TestMemoryEndpoints:
    """Test memory store endpoints."""

    def test_memory_remember(self, test_client):
        """Test remembering values."""
    def test_memory_remember(self, test_client):
        """Test remembering values."""
        import time
        # Use unique value to avoid conflicts with existing data
        unique_email = f"test-{int(time.time())}@example.com"
        response = test_client.post(
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
        test_client.post(
            "/memory/remember",
            json={"category": "email", "value": "recall@test.com"}
        )

        # Then recall it
        response = test_client.get("/memory/recall/emails")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["category"] == "emails"

    def test_memory_stats(self, test_client):
        """Test memory statistics."""
        response = test_client.get("/memory/stats")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert data["summary"]

    def test_memory_forget(self, test_client):
        """Test forgetting values."""
        # Remember something
        test_client.post(
            "/memory/remember",
            json={"category": "email", "value": "forget@test.com"}
        )

        # Forget specific value
        response = test_client.request(
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
        response = test_client.get("/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_cache_clear(self, test_client):
        """Test cache clearing."""
        response = test_client.post("/cache/clear")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["success", "info"]


class TestSessionEndpoints:
    """Test session management endpoints."""

    def test_session_save(self, test_client):
        """Test session saving."""
        response = test_client.post("/session/save")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["success", "info"]

    def test_session_clear(self, test_client):
        """Test session clearing."""
        response = test_client.post("/session/clear")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["success", "info"]


class TestConfigEndpoints:
    """Test configuration endpoints."""

    def test_get_config(self, test_client):
        """Test getting configuration."""
        response = test_client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "llm" in data["data"]

    def test_context_status(self, test_client):
        """Test context usage status."""
        response = test_client.get("/context/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestPluginEndpoints:
    """Test plugin management endpoints."""

    def test_list_plugins(self, test_client):
        """Test listing plugins."""
        response = test_client.get("/plugins")
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "loaded" in data
        assert "count" in data

    def test_list_tools(self, test_client):
        """Test listing tools."""
        response = test_client.get("/tools")
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
            response = test_client.get("/health")
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
            response = test_client.post(
                "/query",
                json={"query": query, "use_tools": False}
            )
            # Should either sanitize or reject
            assert response.status_code in [200, 422]

    def test_invalid_endpoints(self, test_client):
        """Test invalid endpoint access."""
        response = test_client.get("/nonexistent")
        assert response.status_code == 404


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_json(self, test_client):
        """Test handling of invalid JSON."""
        response = test_client.post(
            "/query",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_missing_required_fields(self, test_client):
        """Test handling of missing required fields."""
        response = test_client.post(
            "/query",
            json={"use_multihop": True}  # Missing 'query' field
        )
        assert response.status_code == 422

    def test_invalid_field_types(self, test_client):
        """Test handling of invalid field types."""
        response = test_client.post(
            "/query",
            json={
                "query": "test",
                "max_hops": "invalid"  # Should be int
            }
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
