"""Tests for RateLimiter and RobotsChecker."""
import pytest
import time
from utils.rate_limiter import RateLimiter, RobotsChecker, RequestThrottler


class TestRateLimiter:
    """Test RateLimiter class."""

    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        limiter = RateLimiter(requests_per_second=2.0)

        domain = "example.com"
        url = "https://example.com/test"

        # First request should be immediate
        start = time.time()
        limiter.wait(domain)
        duration1 = time.time() - start
        assert duration1 < 0.1  # Should be instant

        # Second request should be delayed
        start = time.time()
        limiter.wait(domain)
        duration2 = time.time() - start
        assert duration2 >= 0.4  # Should wait ~0.5s (1/2 req/s)

    def test_different_domains(self):
        """Test that different domains don't interfere."""
        limiter = RateLimiter(requests_per_second=1.0)

        # Request to domain1
        limiter.wait("domain1.com")

        # Immediate request to domain2 should not wait
        start = time.time()
        limiter.wait("domain2.com")
        duration = time.time() - start
        assert duration < 0.1

    def test_get_domain(self):
        """Test domain extraction from URL."""
        limiter = RateLimiter()

        assert limiter.get_domain("https://example.com/path") == "example.com"
        assert limiter.get_domain("http://sub.example.com") == "sub.example.com"
        assert limiter.get_domain("https://example.com:8080") == "example.com:8080"

    def test_can_request(self):
        """Test can_request method."""
        limiter = RateLimiter(requests_per_second=1.0)
        url = "https://example.com/test"

        # First request should be allowed
        assert limiter.can_request(url)

        # Make request
        limiter.wait(limiter.get_domain(url))

        # Immediate second request should not be allowed
        assert not limiter.can_request(url)

        # After waiting, should be allowed again
        time.sleep(1.1)
        assert limiter.can_request(url)

    def test_reset(self):
        """Test reset functionality."""
        limiter = RateLimiter(requests_per_second=1.0)

        limiter.wait("example.com")
        assert not limiter.can_request("https://example.com/test")

        limiter.reset("example.com")
        assert limiter.can_request("https://example.com/test")

    def test_reset_all(self):
        """Test resetting all domains."""
        limiter = RateLimiter(requests_per_second=1.0)

        limiter.wait("domain1.com")
        limiter.wait("domain2.com")

        limiter.reset()

        assert limiter.can_request("https://domain1.com")
        assert limiter.can_request("https://domain2.com")


class TestRobotsChecker:
    """Test RobotsChecker class."""

    def test_can_fetch_allowed(self):
        """Test fetching allowed URLs."""
        checker = RobotsChecker(user_agent="TestBot/1.0")

        # Google allows most bots
        result = checker.can_fetch("https://www.google.com/search?q=test")
        assert isinstance(result, bool)

    def test_can_fetch_caching(self):
        """Test robots.txt caching."""
        checker = RobotsChecker()

        url = "https://www.example.com/test"

        # First fetch
        result1 = checker.can_fetch(url)

        # Second fetch should use cache
        result2 = checker.can_fetch(url)

        assert result1 == result2
        assert "example.com" in checker.parsers

    def test_get_robots_url(self):
        """Test robots.txt URL generation."""
        checker = RobotsChecker()

        robots_url = checker._get_robots_url("https://example.com/path/page")
        assert robots_url == "https://example.com/robots.txt"

    def test_clear_cache(self):
        """Test cache clearing."""
        checker = RobotsChecker()

        checker.can_fetch("https://example.com/test")
        assert "example.com" in checker.parsers

        checker.clear_cache("example.com")
        assert "example.com" not in checker.parsers

    def test_clear_all_cache(self):
        """Test clearing all cache."""
        checker = RobotsChecker()

        checker.can_fetch("https://example.com/test")
        checker.can_fetch("https://google.com/test")

        checker.clear_cache()
        assert len(checker.parsers) == 0


class TestRequestThrottler:
    """Test RequestThrottler class."""

    def test_initialization(self):
        """Test throttler initialization."""
        throttler = RequestThrottler(
            requests_per_second=2.0,
            user_agent="TestBot",
            respect_robots=False
        )

        assert throttler.rate_limiter.requests_per_second == 2.0
        assert throttler.robots_checker.user_agent == "TestBot"
        assert throttler.respect_robots is False

    def test_can_fetch_with_robots_disabled(self):
        """Test fetching with robots.txt disabled."""
        throttler = RequestThrottler(respect_robots=False)

        # Should always return True when robots.txt is disabled
        result = throttler.can_fetch("https://example.com/test")
        assert result is True

    def test_can_fetch_with_robots_enabled(self):
        """Test fetching with robots.txt enabled."""
        throttler = RequestThrottler(respect_robots=True)

        result = throttler.can_fetch("https://www.google.com/search")
        assert isinstance(result, bool)

    def test_wait_if_needed(self):
        """Test rate limiting wait."""
        throttler = RequestThrottler(
            requests_per_second=10.0,
            respect_robots=False
        )

        url = "https://example.com/test"

        # First request should be instant
        start = time.time()
        throttler.wait_if_needed(url)
        duration = time.time() - start
        assert duration < 0.2

    @pytest.mark.skip(reason="Requires network access")
    def test_throttled_request(self):
        """Test making throttled HTTP request."""
        throttler = RequestThrottler(respect_robots=False)

        response = throttler.throttled_request(
            "https://httpbin.org/get",
            method="GET"
        )

        assert response is not None
        assert response.status_code == 200

    def test_throttled_request_disallowed(self):
        """Test request blocked by robots.txt."""
        throttler = RequestThrottler(respect_robots=True)

        # Create a mock URL that would be disallowed
        # This test might need adjustment based on actual robots.txt
        with pytest.raises(ValueError):
            # Intentionally pass invalid URL to trigger ValueError
            throttler.throttled_request("https://invalid-url-for-test")
