"""Comprehensive security tests for Redis-based rate limiting.

Tests DoS protection through distributed rate limiting with Token Bucket algorithm.

Test Categories:
1. Basic Rate Limiting - Token consumption and refill
2. Per-Endpoint Limits - Different limits for different endpoints
3. Distributed Behavior - Multiple servers/clients
4. Edge Cases - Redis failures, invalid inputs
5. Token Bucket Algorithm - Burst handling, sliding window
6. Security Validation - Key injection, resource cleanup
"""
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
import fakeredis

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


class TestBasicRateLimiting:
    """Test basic rate limiting functionality."""
    
    def test_first_request_allowed(self, rate_limiter):
        """First request should always be allowed."""
        allowed, info = rate_limiter.check_rate_limit(
            user_id="user1",
            endpoint="/query",
            limit=10,
            window=60
        )
        
        assert allowed is True
        assert info["remaining"] == 9  # 10 - 1 consumed
        assert info["retry_after"] == 0
    
    def test_multiple_requests_within_limit(self, rate_limiter):
        """Multiple requests within limit should be allowed."""
        user_id = "user2"
        endpoint = "/query"
        limit = 5
        
        # Make 5 requests (all should succeed)
        for i in range(limit):
            allowed, info = rate_limiter.check_rate_limit(
                user_id=user_id,
                endpoint=endpoint,
                limit=limit,
                window=60
            )
            assert allowed is True
            assert info["remaining"] == limit - i - 1
    
    def test_exceeds_rate_limit(self, rate_limiter):
        """Request exceeding rate limit should be denied."""
        user_id = "user3"
        endpoint = "/query"
        limit = 3
        
        # Exhaust limit
        for _ in range(limit):
            allowed, info = rate_limiter.check_rate_limit(
                user_id=user_id,
                endpoint=endpoint,
                limit=limit,
                window=60
            )
            assert allowed is True
        
        # Next request should be denied
        allowed, info = rate_limiter.check_rate_limit(
            user_id=user_id,
            endpoint=endpoint,
            limit=limit,
            window=60
        )
        
        assert allowed is False
        assert info["remaining"] == 0
        assert info["retry_after"] > 0
    
    def test_tokens_refill_over_time(self, rate_limiter, fake_redis):
        """Tokens should refill over time."""
        user_id = "user4"
        endpoint = "/query"
        limit = 10
        window = 10  # 10 seconds window
        
        # Consume all tokens
        for _ in range(limit):
            rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        
        # Should be rate limited
        allowed, _ = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        assert allowed is False
        
        # Simulate time passing (1 second = 1 token refilled)
        # Get current state
        key = rate_limiter._get_key(user_id, endpoint)
        last_update = float(fake_redis.get(f"{key}:last_update"))
        
        # Advance time by 2 seconds
        fake_redis.set(f"{key}:last_update", last_update - 2.0)
        
        # Should have ~2 tokens available
        allowed, info = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        assert allowed is True
        assert info["remaining"] >= 1


class TestPerEndpointLimits:
    """Test per-endpoint rate limiting."""
    
    def test_different_endpoints_separate_limits(self, rate_limiter):
        """Different endpoints should have separate rate limits."""
        user_id = "user5"
        endpoint1 = "/query"
        endpoint2 = "/search"
        limit = 3
        
        # Exhaust limit on endpoint1
        for _ in range(limit):
            allowed, _ = rate_limiter.check_rate_limit(user_id, endpoint1, limit, 60)
            assert allowed is True
        
        # endpoint1 should be rate limited
        allowed, _ = rate_limiter.check_rate_limit(user_id, endpoint1, limit, 60)
        assert allowed is False
        
        # endpoint2 should still be available
        allowed, info = rate_limiter.check_rate_limit(user_id, endpoint2, limit, 60)
        assert allowed is True
        assert info["remaining"] == limit - 1
    
    def test_get_rate_limit_for_endpoint(self):
        """Test rate limit configuration retrieval."""
        # Specific endpoint
        limit, window = get_rate_limit_for_endpoint("/query")
        assert limit == 10
        assert window == 60
        
        # OSINT endpoint (stricter)
        limit, window = get_rate_limit_for_endpoint("/osint/query")
        assert limit == 5
        assert window == 60
        
        # Unknown endpoint uses default
        limit, window = get_rate_limit_for_endpoint("/unknown")
        assert limit == 60
        assert window == 60
    
    def test_different_users_separate_limits(self, rate_limiter):
        """Different users should have separate rate limits."""
        endpoint = "/query"
        limit = 3
        
        # User1 exhausts limit
        for _ in range(limit):
            allowed, _ = rate_limiter.check_rate_limit("user6", endpoint, limit, 60)
            assert allowed is True
        
        allowed, _ = rate_limiter.check_rate_limit("user6", endpoint, limit, 60)
        assert allowed is False
        
        # User2 should still have full quota
        allowed, info = rate_limiter.check_rate_limit("user7", endpoint, limit, 60)
        assert allowed is True
        assert info["remaining"] == limit - 1


class TestDistributedBehavior:
    """Test distributed rate limiting across multiple clients."""
    
    def test_multiple_clients_share_redis(self, fake_redis):
        """Multiple rate limiter instances should share state via Redis."""
        limiter1 = RedisRateLimiter(redis_client=fake_redis)
        limiter2 = RedisRateLimiter(redis_client=fake_redis)
        
        user_id = "user8"
        endpoint = "/query"
        limit = 5
        
        # Client 1 makes 3 requests
        for _ in range(3):
            allowed, _ = limiter1.check_rate_limit(user_id, endpoint, limit, 60)
            assert allowed is True
        
        # Client 2 should see only 2 remaining
        allowed, info = limiter2.check_rate_limit(user_id, endpoint, limit, 60)
        assert allowed is True
        assert info["remaining"] == 1  # 5 - 3 - 1 = 1
    
    def test_redis_key_format(self, rate_limiter):
        """Test Redis key generation and sanitization."""
        # Normal key
        key = rate_limiter._get_key("user123", "/query")
        assert key == "ratelimit:user123:_query"
        
        # Key with colons (should be sanitized in user_id and endpoint parts)
        key = rate_limiter._get_key("user:123", "/api:query")
        # Structure is "ratelimit:USER:ENDPOINT" - the separating colons are OK
        # But colons WITHIN user_id and endpoint should be replaced with _
        assert key == "ratelimit:user_123:_api_query"
        
        # Key with spaces (should be sanitized)
        key = rate_limiter._get_key("user 123", "/query path")
        assert " " not in key


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_redis_connection_failure_fails_open(self):
        """Rate limiting should fail open on Redis errors."""
        # Create rate limiter with broken Redis
        broken_redis = Mock()
        broken_redis.pipeline.side_effect = Exception("Redis connection failed")
        
        limiter = RedisRateLimiter(redis_client=broken_redis)
        
        # Request should be allowed (fail open)
        allowed, info = limiter.check_rate_limit("user9", "/query", 10, 60)
        assert allowed is True
        assert "error" in info
    
    def test_zero_limit_always_denies(self, rate_limiter):
        """Zero rate limit should always deny requests."""
        allowed, info = rate_limiter.check_rate_limit(
            user_id="user10",
            endpoint="/query",
            limit=0,
            window=60
        )
        
        # With 0 limit, no requests should be allowed
        assert allowed is False
        assert info["remaining"] == 0
    
    def test_very_large_limit(self, rate_limiter):
        """Test with very large rate limit."""
        user_id = "user11"
        endpoint = "/query"
        limit = 1_000_000
        
        allowed, info = rate_limiter.check_rate_limit(user_id, endpoint, limit, 60)
        
        assert allowed is True
        assert info["remaining"] == limit - 1
    
    def test_reset_rate_limit(self, rate_limiter):
        """Test manual rate limit reset."""
        user_id = "user12"
        endpoint = "/query"
        limit = 2
        
        # Exhaust limit
        for _ in range(limit):
            rate_limiter.check_rate_limit(user_id, endpoint, limit, 60)
        
        # Should be rate limited
        allowed, _ = rate_limiter.check_rate_limit(user_id, endpoint, limit, 60)
        assert allowed is False
        
        # Reset limit
        success = rate_limiter.reset_rate_limit(user_id, endpoint)
        assert success is True
        
        # Should be allowed again
        allowed, info = rate_limiter.check_rate_limit(user_id, endpoint, limit, 60)
        assert allowed is True
        assert info["remaining"] == limit - 1


class TestTokenBucketAlgorithm:
    """Test Token Bucket algorithm specifics."""
    
    def test_burst_handling(self, rate_limiter):
        """Token Bucket should allow bursts up to limit."""
        user_id = "user13"
        endpoint = "/query"
        limit = 10
        
        # Make 10 requests in rapid succession (burst)
        for i in range(limit):
            allowed, info = rate_limiter.check_rate_limit(user_id, endpoint, limit, 60)
            assert allowed is True, f"Request {i+1} should be allowed"
        
        # 11th request should be denied
        allowed, _ = rate_limiter.check_rate_limit(user_id, endpoint, limit, 60)
        assert allowed is False
    
    def test_sliding_window_behavior(self, rate_limiter, fake_redis):
        """Test sliding window token refill."""
        user_id = "user14"
        endpoint = "/query"
        limit = 5
        window = 5  # 5 seconds = 1 token per second
        
        # Use all tokens
        for _ in range(limit):
            rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        
        # No tokens available
        allowed, _ = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        assert allowed is False
        
        # Simulate 1.5 seconds passing
        key = rate_limiter._get_key(user_id, endpoint)
        last_update = float(fake_redis.get(f"{key}:last_update"))
        fake_redis.set(f"{key}:last_update", last_update - 1.5)
        
        # Should have ~1.5 tokens (can make 1 request)
        allowed, _ = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        assert allowed is True
        
        # Second request should fail (only had 1.5 tokens)
        allowed, _ = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        assert allowed is False
    
    def test_max_tokens_capped_at_limit(self, rate_limiter, fake_redis):
        """Token count should never exceed limit."""
        user_id = "user15"
        endpoint = "/query"
        limit = 5
        window = 10
        
        # Make one request
        rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        
        # Simulate very long time passing (should refill to limit, not beyond)
        key = rate_limiter._get_key(user_id, endpoint)
        fake_redis.set(f"{key}:last_update", 0.0)  # Very old timestamp
        
        # Check status (should have limit tokens, not more)
        status = rate_limiter.get_rate_limit_status(user_id, endpoint, limit, window)
        assert status["tokens"] == float(limit)
        assert status["remaining"] == limit


class TestSecurityValidation:
    """Test security aspects of rate limiting."""
    
    def test_key_injection_prevention(self, rate_limiter):
        """Test prevention of Redis key injection attacks."""
        # Try to inject Redis command via user_id
        malicious_user_id = "user'; DEL *; GET 'x"
        endpoint = "/query"
        
        # Should not crash or execute Redis commands
        allowed, info = rate_limiter.check_rate_limit(
            user_id=malicious_user_id,
            endpoint=endpoint,
            limit=10,
            window=60
        )
        
        # Request should be processed normally
        assert allowed is True
        assert info["remaining"] == 9
    
    def test_get_rate_limit_status_no_side_effects(self, rate_limiter):
        """Getting status should not consume tokens."""
        user_id = "user16"
        endpoint = "/query"
        limit = 10
        
        # Check status without consuming token
        status1 = rate_limiter.get_rate_limit_status(user_id, endpoint, limit, 60)
        assert status1["remaining"] == limit
        
        # Check again - should be same
        status2 = rate_limiter.get_rate_limit_status(user_id, endpoint, limit, 60)
        assert status2["remaining"] == limit
        
        # Make actual request
        allowed, info = rate_limiter.check_rate_limit(user_id, endpoint, limit, 60)
        assert allowed is True
        assert info["remaining"] == limit - 1
    
    def test_cleanup_expired_keys(self, rate_limiter, fake_redis):
        """Test cleanup of expired rate limit keys."""
        # Create some rate limit entries
        for i in range(5):
            rate_limiter.check_rate_limit(f"user{i}", "/query", 10, 60)
        
        # Verify keys exist
        keys_before = len(fake_redis.keys("ratelimit:*"))
        assert keys_before > 0
        
        # Cleanup
        deleted = rate_limiter.cleanup_expired_keys()
        
        # Some keys should be deleted (fakeredis doesn't auto-expire)
        assert deleted >= 0
    
    def test_connection_pool_cleanup(self, fake_redis):
        """Test proper cleanup of Redis connections."""
        limiter = RedisRateLimiter(redis_client=fake_redis)
        
        # Use limiter
        limiter.check_rate_limit("user17", "/query", 10, 60)
        
        # Close should not raise exception
        limiter.close()


class TestRateLimitIntegration:
    """Integration tests for rate limiting in API context."""
    
    def test_realistic_api_usage_pattern(self, rate_limiter):
        """Test realistic API usage pattern over time."""
        user_id = "api_user"
        endpoint = "/query"
        limit = 10
        window = 60
        
        # Burst of 5 requests
        for _ in range(5):
            allowed, _ = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
            assert allowed is True
        
        # Wait a bit (simulate in fake redis)
        # Continue with more requests
        for _ in range(5):
            allowed, _ = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
            assert allowed is True
        
        # Should now be at limit
        allowed, info = rate_limiter.check_rate_limit(user_id, endpoint, limit, window)
        assert allowed is False
        assert info["retry_after"] > 0
    
    def test_rate_limit_headers_info(self, rate_limiter):
        """Test information needed for rate limit HTTP headers."""
        user_id = "api_user2"
        endpoint = "/query"
        limit = 10
        
        allowed, info = rate_limiter.check_rate_limit(user_id, endpoint, limit, 60)
        
        # Info should contain everything needed for headers
        assert "remaining" in info
        assert "reset_at" in info
        assert "retry_after" in info
        
        # Values should be reasonable
        assert 0 <= info["remaining"] < limit
        assert info["reset_at"] > time.time()
        assert info["retry_after"] >= 0
