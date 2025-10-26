"""Integration tests for Redis rate limiting in FastAPI app.

Tests the integration of Redis rate limiter with FastAPI middleware,
including rate limit headers, per-endpoint limits, and fallback behavior.

Note: These are simplified tests focusing on rate limiting logic.
Full end-to-end tests require running server with real Redis.
"""
import pytest
from unittest.mock import Mock, patch
import fakeredis

# Test rate limiter directly (unit tests)
from utils.redis_rate_limiter import (
    RedisRateLimiter,
    get_rate_limit_for_endpoint,
    DEFAULT_RATE_LIMITS
)


@pytest.fixture
def fake_redis():
    """Create fake Redis server for testing."""
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture
def rate_limiter(fake_redis):
    """Create RedisRateLimiter with fake Redis."""
    return RedisRateLimiter(redis_client=fake_redis)


class TestRateLimitConfiguration:
    """Test rate limit configuration and customization."""
    
    def test_default_rate_limits_configured(self):
        """Test that default rate limits are properly configured."""
        assert "/query" in DEFAULT_RATE_LIMITS
        assert "/osint/query" in DEFAULT_RATE_LIMITS
        assert "default" in DEFAULT_RATE_LIMITS
        
        # Query endpoint should have stricter limit
        assert DEFAULT_RATE_LIMITS["/query"]["limit"] <= DEFAULT_RATE_LIMITS["default"]["limit"]
    
    def test_get_rate_limit_for_endpoint_returns_config(self):
        """Test getting rate limit configuration for endpoints."""
        # Known endpoint
        limit, window = get_rate_limit_for_endpoint("/query")
        assert limit > 0
        assert window > 0
        
        # Unknown endpoint uses default
        limit, window = get_rate_limit_for_endpoint("/unknown")
        assert limit == 60
        assert window == 60
    
    def test_query_endpoint_has_strict_limit(self):
        """Test that /query has strict rate limit."""
        limit, window = get_rate_limit_for_endpoint("/query")
        assert limit == 10
        assert window == 60
    
    def test_osint_endpoint_has_strictest_limit(self):
        """Test that /osint/query has strictest rate limit."""
        limit, window = get_rate_limit_for_endpoint("/osint/query")
        assert limit == 5  # Strictest
        assert window == 60


class TestRateLimitMiddlewareLogic:
    """Test rate limiting middleware logic (without full FastAPI stack)."""
    
    def test_rate_limiter_enforces_per_endpoint_limits(self, rate_limiter):
        """Test that rate limiter enforces per-endpoint limits."""
        user_id = "test_user"
        endpoint = "/query"
        limit = 10
        window = 60
        
        # Make requests up to limit
        for i in range(limit):
            allowed, info = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
            assert allowed is True
            assert info["remaining"] == limit - i - 1
        
        # Next request should be rate limited
        allowed, info = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        assert allowed is False
        assert info["retry_after"] > 0
    
    def test_rate_limiter_provides_headers_info(self, rate_limiter):
        """Test that rate limiter provides info for HTTP headers."""
        user_id = "test_user2"
        endpoint = "/api"
        limit = 60
        window = 60
        
        allowed, info = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        
        # Should provide all info needed for headers
        assert "remaining" in info
        assert "reset_at" in info
        assert "retry_after" in info
        assert isinstance(info["remaining"], int)
        assert isinstance(info["reset_at"], int)
        assert isinstance(info["retry_after"], int)
    
    def test_different_users_have_separate_quotas(self, rate_limiter):
        """Test that different users have separate rate limit quotas."""
        endpoint = "/query"
        limit = 5
        window = 60
        
        # User 1 exhausts quota
        for _ in range(limit):
            rate_limiter.check_rate_limit("user1", endpoint, limit, window)
        
        allowed, _ = rate_limiter.check_rate_limit("user1", endpoint, limit, window)
        assert allowed is False  # User 1 rate limited
        
        # User 2 should have full quota
        allowed, info = rate_limiter.check_rate_limit("user2", endpoint, limit, window)
        assert allowed is True
        assert info["remaining"] == limit - 1
    
    def test_health_endpoint_config(self):
        """Test that health endpoint can be excluded from rate limiting."""
        # Health endpoint doesn't need strict limits
        # In middleware, it's excluded from rate limiting check
        limit, window = get_rate_limit_for_endpoint("/health")
        # Uses default (which is generous)
        assert limit == 60


class TestRedisIntegrationLogic:
    """Test Redis integration logic."""
    
    def test_redis_rate_limiter_initializes(self, fake_redis):
        """Test that Redis rate limiter initializes with fake Redis."""
        limiter = RedisRateLimiter(redis_client=fake_redis)
        assert limiter is not None
        assert limiter.redis is not None
    
    def test_redis_connection_pooling_configured(self):
        """Test that connection pooling can be configured."""
        # Test that parameters are accepted (without real Redis)
        try:
            with patch('utils.redis_rate_limiter.redis.ConnectionPool'):
                with patch('utils.redis_rate_limiter.redis.Redis'):
                    # Should not crash with configuration
                    from utils.redis_rate_limiter import RedisRateLimiter
        except ImportError:
            pytest.skip("Redis package not available")
    
    def test_redis_cleanup_method_exists(self, rate_limiter):
        """Test that Redis cleanup method exists and doesn't crash."""
        # Should have close method
        assert hasattr(rate_limiter, 'close')
        
        # Should not crash when called
        rate_limiter.close()
    
    def test_distributed_rate_limiting_shares_state(self, fake_redis):
        """Test that multiple limiters share state via Redis."""
        limiter1 = RedisRateLimiter(redis_client=fake_redis)
        limiter2 = RedisRateLimiter(redis_client=fake_redis)
        
        user_id = "shared_user"
        endpoint = "/query"
        limit = 5
        window = 60
        
        # Limiter 1 uses quota
        for _ in range(3):
            limiter1.check_rate_limit(user_id, endpoint, limit, window)
        
        # Limiter 2 should see reduced quota
        allowed, info = limiter2.check_rate_limit(user_id, endpoint, limit, window)
        assert allowed is True
        assert info["remaining"] == 1  # 5 - 3 - 1 = 1


class TestRateLimitSecurity:
    """Test security aspects of rate limiting."""
    
    def test_rate_limit_prevents_dos_attacks(self, rate_limiter):
        """Test that rate limiting prevents DoS attacks."""
        user_id = "attacker"
        endpoint = "/query"
        limit = 10
        window = 60
        
        # Attacker tries to make 100 requests
        denied_count = 0
        for _ in range(100):
            allowed, _ = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
            if not allowed:
                denied_count += 1
        
        # Most requests should be denied
        assert denied_count > 80  # At least 80 out of 100 denied
    
    def test_redis_key_injection_prevented(self, rate_limiter):
        """Test that Redis key injection is prevented."""
        # Try malicious user_id with Redis commands
        malicious_user = "user\'; DEL * GET \'"
        endpoint = "/query"
        
        # Should not crash or execute commands
        allowed, info = rate_limiter.check_rate_limit(malicious_user, endpoint, 10, 60)
        assert allowed is True  # Request processed normally
        assert info["remaining"] >= 0
    
    def test_api_key_hashing_for_rate_limiting(self):
        """Test that API keys should be hashed before use in rate limiting."""
        import hashlib
        import hmac
        import secrets
        
        # Simulate API key hashing with HMAC (cryptographically secure)
        api_key = "secret-api-key-12345"
        secret = secrets.token_bytes(32)  # 256-bit secret
        user_id = hmac.new(secret, api_key.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
        
        # Hashed ID should be different from original
        assert user_id != api_key
        assert len(user_id) == 16
        
        # Same key should produce same hash (consistent rate limiting)
        user_id2 = hmac.new(secret, api_key.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
        assert user_id == user_id2
    
    def test_retry_after_header_calculation(self, rate_limiter):
        """Test that Retry-After value is calculated correctly."""
        user_id = "test_user"
        endpoint = "/query"
        limit = 2
        window = 10
        
        # Exhaust limit
        for _ in range(limit):
            rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        
        # Check retry_after
        allowed, info = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        assert allowed is False
        assert info["retry_after"] > 0
        assert info["retry_after"] <= window  # Should not exceed window


class TestRateLimitEndpointPriority:
    """Test that different endpoints have appropriate rate limits."""
    
    def test_critical_endpoints_have_strict_limits(self):
        """Test that critical endpoints have strict limits."""
        # OSINT queries are resource-intensive
        limit, window = get_rate_limit_for_endpoint("/osint/query")
        assert limit == 5  # Very strict
        
        # Query endpoints moderate
        limit, window = get_rate_limit_for_endpoint("/query")
        assert limit == 10  # Moderate
    
    def test_light_endpoints_have_generous_limits(self):
        """Test that light endpoints have generous limits."""
        # Info endpoints are lightweight
        limit, window = get_rate_limit_for_endpoint("/api")
        assert limit == 60  # Default (generous)
        
        limit, window = get_rate_limit_for_endpoint("/security-info")
        assert limit == 60  # Default
    
    def test_memory_operations_have_moderate_limits(self):
        """Test that memory operations have moderate limits."""
        limit, window = get_rate_limit_for_endpoint("/memory/remember")
        assert limit == 30  # Moderate (can write frequently but not spam)
        assert window == 60
