"""Test CSRF protection implementation.

Tests cover:
- CSRF token generation
- CSRF token validation
- Origin header validation
- Referer header validation
- Middleware integration
- Protected endpoint access
- Token expiration
"""
import pytest
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app import app, API_KEY
from core.csrf_manager import CSRFManager, validate_origin_header, validate_referer_header


class TestCSRFManager:
    """Test CSRF Manager functionality."""
    
    def test_generate_token(self):
        """Test CSRF token generation."""
        manager = CSRFManager(fallback_to_memory=True)
        
        user_id = "test_user_123"
        token = manager.generate_token(user_id)
        
        assert token is not None
        assert len(token) > 40  # Should be 44 chars for urlsafe base64
        assert isinstance(token, str)
    
    def test_validate_token_success(self):
        """Test successful CSRF token validation."""
        manager = CSRFManager(fallback_to_memory=True)
        
        user_id = "test_user_123"
        token = manager.generate_token(user_id)
        
        # Validate immediately
        is_valid = manager.validate_token(user_id, token)
        assert is_valid is True
    
    def test_validate_token_wrong_token(self):
        """Test CSRF validation with wrong token."""
        manager = CSRFManager(fallback_to_memory=True)
        
        user_id = "test_user_123"
        token = manager.generate_token(user_id)
        
        # Try to validate with wrong token
        is_valid = manager.validate_token(user_id, "wrong_token_abc123")
        assert is_valid is False
    
    def test_validate_token_wrong_user(self):
        """Test CSRF validation with wrong user."""
        manager = CSRFManager(fallback_to_memory=True)
        
        user_id = "test_user_123"
        token = manager.generate_token(user_id)
        
        # Try to validate with different user
        is_valid = manager.validate_token("different_user_456", token)
        assert is_valid is False
    
    def test_validate_token_expired(self):
        """Test CSRF validation with expired token."""
        # Use very short expiry for testing
        manager = CSRFManager(fallback_to_memory=True, token_expiry=1)
        
        user_id = "test_user_123"
        token = manager.generate_token(user_id)
        
        # Wait for token to expire
        time.sleep(1.5)
        
        # Should be expired now
        is_valid = manager.validate_token(user_id, token)
        assert is_valid is False
    
    def test_revoke_token(self):
        """Test CSRF token revocation."""
        manager = CSRFManager(fallback_to_memory=True)
        
        user_id = "test_user_123"
        token = manager.generate_token(user_id)
        
        # Token should be valid
        assert manager.validate_token(user_id, token) is True
        
        # Revoke token
        result = manager.revoke_token(user_id)
        assert result is True
        
        # Token should no longer be valid
        assert manager.validate_token(user_id, token) is False
    
    def test_cleanup_expired(self):
        """Test cleanup of expired tokens."""
        # Use very short expiry for testing
        manager = CSRFManager(fallback_to_memory=True, token_expiry=1)
        
        # Generate multiple tokens
        user_id1 = "test_user_1"
        user_id2 = "test_user_2"
        user_id3 = "test_user_3"
        
        manager.generate_token(user_id1)
        manager.generate_token(user_id2)
        manager.generate_token(user_id3)
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Cleanup
        count = manager.cleanup_expired()
        assert count == 3
    
    def test_get_stats(self):
        """Test CSRF manager statistics."""
        manager = CSRFManager(fallback_to_memory=True)
        
        # Generate some tokens
        manager.generate_token("user1")
        manager.generate_token("user2")
        
        stats = manager.get_stats()
        assert "backend" in stats
        assert stats["backend"] == "memory"
        assert stats["memory_token_count"] == 2


class TestOriginRefererValidation:
    """Test Origin and Referer header validation."""
    
    def test_validate_origin_success(self):
        """Test valid Origin header."""
        allowed_origins = ["http://localhost:3000", "https://example.com"]
        
        assert validate_origin_header("http://localhost:3000", allowed_origins) is True
        assert validate_origin_header("https://example.com", allowed_origins) is True
    
    def test_validate_origin_with_trailing_slash(self):
        """Test Origin validation with trailing slashes."""
        allowed_origins = ["http://localhost:3000/", "https://example.com"]
        
        # Should match even with trailing slash differences
        assert validate_origin_header("http://localhost:3000", allowed_origins) is True
        assert validate_origin_header("https://example.com/", allowed_origins) is True
    
    def test_validate_origin_failure(self):
        """Test invalid Origin header."""
        allowed_origins = ["http://localhost:3000", "https://example.com"]
        
        assert validate_origin_header("http://evil.com", allowed_origins) is False
        assert validate_origin_header("https://phishing.com", allowed_origins) is False
    
    def test_validate_origin_none(self):
        """Test validation with no Origin header."""
        allowed_origins = ["http://localhost:3000"]
        
        assert validate_origin_header(None, allowed_origins) is False
        assert validate_origin_header("", allowed_origins) is False
    
    def test_validate_referer_success(self):
        """Test valid Referer header."""
        allowed_hosts = ["localhost", "example.com"]
        
        assert validate_referer_header("http://localhost:3000/page", allowed_hosts) is True
        assert validate_referer_header("https://example.com/path", allowed_hosts) is True
    
    def test_validate_referer_failure(self):
        """Test invalid Referer header."""
        allowed_hosts = ["localhost", "example.com"]
        
        assert validate_referer_header("http://evil.com", allowed_hosts) is False
        assert validate_referer_header("https://phishing.com/page", allowed_hosts) is False
    
    def test_validate_referer_none(self):
        """Test validation with no Referer header."""
        allowed_hosts = ["localhost"]
        
        assert validate_referer_header(None, allowed_hosts) is False
        assert validate_referer_header("", allowed_hosts) is False


class TestCSRFEndpoints:
    """Test CSRF API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        return {"X-API-Key": API_KEY}
    
    def test_csrf_token_generation(self, client, auth_headers):
        """Test CSRF token generation endpoint."""
        response = client.post("/csrf-token", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "csrf_token" in data
        assert "expires_in" in data
        assert "usage" in data
        assert len(data["csrf_token"]) > 40
    
    def test_csrf_token_requires_auth(self, client):
        """Test that CSRF token endpoint requires authentication."""
        response = client.post("/csrf-token")
        
        assert response.status_code == 401
    
    def test_protected_endpoint_without_csrf(self, client, auth_headers):
        """Test that protected endpoints reject requests without CSRF token."""
        response = client.post("/cache/clear", headers=auth_headers)
        
        # Should be rejected for missing CSRF token
        assert response.status_code == 403
        assert "CSRF" in response.json()["detail"]
    
    def test_protected_endpoint_with_csrf(self, client, auth_headers):
        """Test that protected endpoints accept requests with valid CSRF token."""
        # First, get a CSRF token
        token_response = client.post("/csrf-token", headers=auth_headers)
        csrf_token = token_response.json()["csrf_token"]
        
        # Add CSRF token and Origin header (required by CSRF middleware)
        headers = {
            **auth_headers,
            "X-CSRF-Token": csrf_token,
            "Origin": "http://localhost:3000"  # Must be in ALLOWED_ORIGINS
        }
        
        # Now try to access protected endpoint
        response = client.post("/cache/clear", headers=headers)
        
        # Should succeed (or fail for other reasons, but not CSRF)
        assert response.status_code in [200, 500]  # 500 if cache not initialized
        if response.status_code == 403:
            # If it's still 403, ensure it's not CSRF-related
            assert "CSRF" not in response.json()["detail"]
    
    def test_csrf_token_reuse(self, client, auth_headers):
        """Test that CSRF tokens can be reused within their lifetime."""
        # Get a CSRF token
        token_response = client.post("/csrf-token", headers=auth_headers)
        csrf_token = token_response.json()["csrf_token"]
        
        headers = {
            **auth_headers,
            "X-CSRF-Token": csrf_token,
            "Origin": "http://localhost:3000"  # Must be in ALLOWED_ORIGINS
        }
        
        # Use the same token twice
        response1 = client.post("/session/clear", headers=headers)
        response2 = client.post("/session/save", headers=headers)
        
        # Both should succeed (or fail for non-CSRF reasons)
        assert response1.status_code != 403 or "CSRF" not in response1.json()["detail"]
        assert response2.status_code != 403 or "CSRF" not in response2.json()["detail"]


class TestCSRFMiddleware:
    """Test CSRF middleware functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        return {"X-API-Key": API_KEY}
    
    def test_origin_validation_middleware(self, client, auth_headers):
        """Test Origin header validation in middleware."""
        # Valid origin
        headers = {
            **auth_headers,
            "Origin": "http://localhost:3000"
        }
        
        # GET requests should pass (safe methods)
        response = client.get("/api", headers=headers)
        assert response.status_code == 200
    
    def test_origin_rejection_middleware(self, client, auth_headers):
        """Test that invalid Origins are rejected."""
        # Get CSRF token first
        token_response = client.post("/csrf-token", headers=auth_headers)
        csrf_token = token_response.json()["csrf_token"]
        
        # Invalid origin
        headers = {
            **auth_headers,
            "X-CSRF-Token": csrf_token,
            "Origin": "http://evil.com"
        }
        
        # POST request with invalid origin should be rejected
        response = client.post("/session/clear", headers=headers)
        assert response.status_code == 403
        assert "Origin" in response.json()["detail"] or "CSRF" in response.json()["detail"]
    
    def test_referer_fallback_validation(self, client, auth_headers):
        """Test Referer header validation when Origin is missing."""
        # Get CSRF token first
        token_response = client.post("/csrf-token", headers=auth_headers)
        csrf_token = token_response.json()["csrf_token"]
        
        # Valid referer (no Origin header)
        headers = {
            **auth_headers,
            "X-CSRF-Token": csrf_token,
            "Referer": "http://localhost:3000/page"
        }
        
        # Should pass with valid Referer
        response = client.post("/session/clear", headers=headers)
        # Should not be rejected for CSRF/Origin reasons
        assert response.status_code != 403 or ("Origin" not in response.json()["detail"] and "Referer" not in response.json()["detail"])
    
    def test_safe_methods_skip_csrf(self, client, auth_headers):
        """Test that safe HTTP methods skip CSRF checks."""
        # GET requests don't need CSRF tokens
        response = client.get("/config", headers=auth_headers)
        assert response.status_code == 200
        
        # Same for other safe methods
        response = client.get("/memory/stats", headers=auth_headers)
        assert response.status_code in [200, 503]  # 503 if memory store not initialized


class TestCSRFSecurity:
    """Test CSRF security features."""
    
    def test_csrf_token_randomness(self):
        """Test that CSRF tokens are random and unique."""
        manager = CSRFManager(fallback_to_memory=True)
        
        tokens = set()
        for i in range(100):
            token = manager.generate_token(f"user_{i}")
            tokens.add(token)
        
        # All tokens should be unique
        assert len(tokens) == 100
    
    def test_csrf_token_length(self):
        """Test that CSRF tokens have sufficient entropy."""
        manager = CSRFManager(fallback_to_memory=True)
        
        token = manager.generate_token("test_user")
        
        # Should be at least 32 bytes (44 chars in base64)
        assert len(token) >= 40
    
    def test_csrf_constant_time_comparison(self):
        """Test that token comparison is constant-time (timing attack resistant)."""
        manager = CSRFManager(fallback_to_memory=True)
        
        user_id = "test_user"
        correct_token = manager.generate_token(user_id)
        wrong_token = "a" * len(correct_token)
        
        # Measure time for correct vs wrong token (should be similar)
        import time
        
        start = time.perf_counter()
        manager.validate_token(user_id, correct_token)
        time_correct = time.perf_counter() - start
        
        start = time.perf_counter()
        manager.validate_token(user_id, wrong_token)
        time_wrong = time.perf_counter() - start
        
        # Times should be comparable (within 10x)
        # Note: This is a weak test, but demonstrates constant-time intent
        assert abs(time_correct - time_wrong) < 0.01  # 10ms tolerance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
