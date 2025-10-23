"""Rate limiting and robots.txt compliance for web requests."""
import time
import requests
from typing import Dict, Optional
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from threading import Lock
from utils.logger import setup_logger

logger = setup_logger(__name__)


class RateLimiter:
    """Rate limiter with per-domain tracking."""

    def __init__(self, requests_per_second: float = 1.0):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second per domain
        """
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time: Dict[str, float] = {}
        self.lock = Lock()

    def wait(self, domain: str):
        """
        Wait if necessary to respect rate limit.

        Args:
            domain: Domain to check
        """
        with self.lock:
            now = time.time()
            last_time = self.last_request_time.get(domain, 0)
            time_since_last = now - last_time

            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                logger.debug(f"Rate limiting {domain}: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)

            self.last_request_time[domain] = time.time()

    def get_domain(self, url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            Domain name
        """
        parsed = urlparse(url)
        return parsed.netloc

    def can_request(self, url: str) -> bool:
        """
        Check if request can be made now without waiting.

        Args:
            url: URL to check

        Returns:
            True if request can be made immediately
        """
        domain = self.get_domain(url)
        with self.lock:
            now = time.time()
            last_time = self.last_request_time.get(domain, 0)
            time_since_last = now - last_time
            return time_since_last >= self.min_interval

    def reset(self, domain: Optional[str] = None):
        """
        Reset rate limiting for domain or all domains.

        Args:
            domain: Domain to reset (or None for all)
        """
        with self.lock:
            if domain:
                self.last_request_time.pop(domain, None)
                logger.debug(f"Reset rate limit for {domain}")
            else:
                self.last_request_time.clear()
                logger.debug("Reset all rate limits")


class RobotsChecker:
    """Check robots.txt compliance for web scraping."""

    def __init__(self, user_agent: str = "CrawlLama/1.0"):
        """
        Initialize robots.txt checker.

        Args:
            user_agent: User agent string
        """
        self.user_agent = user_agent
        self.parsers: Dict[str, RobotFileParser] = {}
        self.cache_ttl = 3600  # 1 hour
        self.last_fetch: Dict[str, float] = {}
        self.lock = Lock()

    def _get_robots_url(self, url: str) -> str:
        """
        Get robots.txt URL for a given URL.

        Args:
            url: Full URL

        Returns:
            robots.txt URL
        """
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def _fetch_robots(self, domain: str, robots_url: str) -> RobotFileParser:
        """
        Fetch and parse robots.txt.

        Args:
            domain: Domain name
            robots_url: URL to robots.txt

        Returns:
            RobotFileParser instance
        """
        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            logger.debug(f"Fetching robots.txt from {robots_url}")
            parser.read()
            self.parsers[domain] = parser
            self.last_fetch[domain] = time.time()
            logger.info(f"✓ Fetched robots.txt for {domain}")

        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")
            # Create permissive parser if fetch fails
            parser = RobotFileParser()
            parser.parse([])  # Empty robots.txt allows everything
            self.parsers[domain] = parser
            self.last_fetch[domain] = time.time()

        return parser

    def can_fetch(self, url: str) -> bool:
        """
        Check if URL can be fetched according to robots.txt.

        Args:
            url: URL to check

        Returns:
            True if URL can be fetched
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        robots_url = self._get_robots_url(url)

        with self.lock:
            # Check cache
            now = time.time()
            if domain in self.parsers:
                last_fetch = self.last_fetch.get(domain, 0)
                if now - last_fetch < self.cache_ttl:
                    parser = self.parsers[domain]
                    can_fetch = parser.can_fetch(self.user_agent, url)
                    logger.debug(f"robots.txt check for {url}: {can_fetch}")
                    return can_fetch

            # Fetch new robots.txt
            parser = self._fetch_robots(domain, robots_url)
            can_fetch = parser.can_fetch(self.user_agent, url)
            logger.debug(f"robots.txt check for {url}: {can_fetch}")
            return can_fetch

    def get_crawl_delay(self, url: str) -> Optional[float]:
        """
        Get crawl delay from robots.txt.

        Args:
            url: URL to check

        Returns:
            Crawl delay in seconds or None
        """
        parsed = urlparse(url)
        domain = parsed.netloc

        with self.lock:
            if domain not in self.parsers:
                robots_url = self._get_robots_url(url)
                self._fetch_robots(domain, robots_url)

            parser = self.parsers.get(domain)
            if parser:
                delay = parser.crawl_delay(self.user_agent)
                return float(delay) if delay else None

        return None

    def clear_cache(self, domain: Optional[str] = None):
        """
        Clear robots.txt cache.

        Args:
            domain: Domain to clear (or None for all)
        """
        with self.lock:
            if domain:
                self.parsers.pop(domain, None)
                self.last_fetch.pop(domain, None)
                logger.debug(f"Cleared robots.txt cache for {domain}")
            else:
                self.parsers.clear()
                self.last_fetch.clear()
                logger.debug("Cleared all robots.txt cache")


class RequestThrottler:
    """Combined rate limiting and robots.txt checking."""

    def __init__(
        self,
        requests_per_second: float = 1.0,
        user_agent: str = "CrawlLama/1.0",
        respect_robots: bool = True
    ):
        """
        Initialize request throttler.

        Args:
            requests_per_second: Maximum requests per second
            user_agent: User agent string
            respect_robots: Whether to check robots.txt
        """
        self.rate_limiter = RateLimiter(requests_per_second)
        self.robots_checker = RobotsChecker(user_agent)
        self.respect_robots = respect_robots

    def can_fetch(self, url: str) -> bool:
        """
        Check if URL can be fetched.

        Args:
            url: URL to check

        Returns:
            True if allowed by robots.txt
        """
        if not self.respect_robots:
            return True

        return self.robots_checker.can_fetch(url)

    def wait_if_needed(self, url: str):
        """
        Wait if necessary for rate limiting.

        Args:
            url: URL to fetch
        """
        domain = self.rate_limiter.get_domain(url)

        # Check for crawl delay from robots.txt
        if self.respect_robots:
            crawl_delay = self.robots_checker.get_crawl_delay(url)
            if crawl_delay:
                logger.debug(f"Using crawl delay from robots.txt: {crawl_delay}s")
                time.sleep(crawl_delay)
                return

        # Use standard rate limiting
        self.rate_limiter.wait(domain)

    def throttled_request(
        self,
        url: str,
        method: str = "GET",
        **kwargs
    ) -> requests.Response:
        """
        Make a throttled HTTP request.

        Args:
            url: URL to fetch
            method: HTTP method
            **kwargs: Additional arguments for requests

        Returns:
            Response object

        Raises:
            ValueError: If URL is disallowed by robots.txt
            requests.RequestException: If request fails
        """
        # Check robots.txt
        if not self.can_fetch(url):
            raise ValueError(f"URL disallowed by robots.txt: {url}")

        # Wait for rate limiting
        self.wait_if_needed(url)

        # Make request
        logger.debug(f"Making {method} request to {url}")
        response = requests.request(method, url, **kwargs)
        return response


# Global throttler instance
throttler = RequestThrottler(
    requests_per_second=1.0,
    user_agent="CrawlLama/1.0 (+https://github.com/arn-c0de/crawllama)",
    respect_robots=True
)
