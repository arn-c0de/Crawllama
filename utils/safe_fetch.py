"""Safe fetch wrapper combining all security and reliability features."""
import logging
import requests
import time
from typing import Optional, Dict, Set
from utils.rate_limiter import throttler
from utils.domain_blacklist import is_url_not_blacklisted
from utils.proxy_validator import ProxyValidator
from utils.logger import setup_logger
from utils.validators import sanitize_url_for_logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

logger = setup_logger(__name__)


class SafeFetcher:
    """Secure HTTP client with all safety features enabled."""

    def __init__(
        self,
        use_rate_limiting: bool = True,
        use_blacklist: bool = True,
        use_robots: bool = True,
        use_proxy: bool = True,
        user_agent: str = "CrawlLama/1.0 (AI Research Tool)",
        circuit_breaker_timeout: int = 300  # 5 minutes default
    ):
        """
        Initialize safe fetcher.

        Args:
            use_rate_limiting: Enable rate limiting
            use_blacklist: Enable domain blacklist
            use_robots: Respect robots.txt
            use_proxy: Use proxy if configured
            user_agent: User agent string
            circuit_breaker_timeout: Seconds to wait before retrying failed domains
        """
        self.use_rate_limiting = use_rate_limiting
        self.use_blacklist = use_blacklist
        self.use_robots = use_robots
        self.use_proxy = use_proxy
        self.user_agent = user_agent
        self.circuit_breaker_timeout = circuit_breaker_timeout

        # Circuit breaker: track failed domains
        self.failed_domains: Dict[str, float] = {}  # domain -> timestamp of last failure
        self.permanent_failures: Set[str] = set()  # domains that consistently fail

        # Load proxy configuration
        self.proxy_validator = ProxyValidator.load_from_env() if use_proxy else None
        self.proxies = self.proxy_validator.get_proxies() if self.proxy_validator else {}

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        return urlparse(url).netloc
    
    def _is_domain_blocked(self, domain: str) -> bool:
        """Check if domain is currently blocked by circuit breaker."""
        current_time = time.time()
        
        # Check permanent failures
        if domain in self.permanent_failures:
            logger.debug(f"Domain {domain} is permanently blocked")
            return True
        
        # Check temporary failures
        if domain in self.failed_domains:
            last_failure = self.failed_domains[domain]
            if current_time - last_failure < self.circuit_breaker_timeout:
                remaining = self.circuit_breaker_timeout - (current_time - last_failure)
                logger.debug(f"Domain {domain} blocked for {remaining:.0f}s more")
                return True
            else:
                # Timeout expired, remove from failed domains
                del self.failed_domains[domain]
        
        return False
    
    def _record_failure(self, domain: str, is_permanent: bool = False):
        """Record a failure for circuit breaker."""
        current_time = time.time()
        
        if is_permanent:
            self.permanent_failures.add(domain)
            logger.warning(f"Domain {domain} marked as permanently failed")
        else:
            # Count consecutive failures
            if domain in self.failed_domains:
                # If this is the 3rd failure within timeout, mark as permanent
                last_failure = self.failed_domains[domain]
                if current_time - last_failure < self.circuit_breaker_timeout:
                    failure_count = getattr(self, '_failure_counts', {}).get(domain, 0) + 1
                    if not hasattr(self, '_failure_counts'):
                        self._failure_counts = {}
                    self._failure_counts[domain] = failure_count
                    
                    if failure_count >= 3:
                        self.permanent_failures.add(domain)
                        logger.warning(f"Domain {domain} failed {failure_count} times - marked as permanent failure")
                        return
            
            self.failed_domains[domain] = current_time
            logger.debug(f"Domain {domain} marked as temporarily failed")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=False
    )
    def _request_with_retry(
        self,
        method: str,
        url: str,
        timeout: int,
        headers: Dict[str, str],
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method
            url: URL to fetch
            timeout: Request timeout
            headers: HTTP headers
            **kwargs: Additional arguments

        Returns:
            Response object

        Raises:
            requests.RequestException: If request fails
        """
        response = requests.request(method, url, timeout=timeout, headers=headers, **kwargs)
        response.raise_for_status()
        return response

    def fetch(
        self,
        url: str,
        method: str = "GET",
        timeout: int = 10,
        **kwargs
    ) -> Optional[requests.Response]:
        """
        Safely fetch a URL with all security features.

        Args:
            url: URL to fetch
            method: HTTP method
            timeout: Request timeout
            **kwargs: Additional arguments for requests

        Returns:
            Response object or None if failed/blocked

        Raises:
            ValueError: If URL is blocked by security checks
        """
        domain = self._get_domain(url)
        
        # Check circuit breaker first
        if self._is_domain_blocked(domain):
            logger.warning(f"URL blocked by circuit breaker: {sanitize_url_for_logging(url)}")
            raise ValueError(f"Domain temporarily unavailable: {domain}")

        # Check blacklist
        if self.use_blacklist and not is_url_not_blacklisted(url):
            logger.warning(f"URL blocked by blacklist: {sanitize_url_for_logging(url)}")
            raise ValueError(f"URL is blacklisted: {domain}")

        # Check robots.txt
        if self.use_robots and not throttler.can_fetch(url):
            logger.warning(f"URL disallowed by robots.txt: {sanitize_url_for_logging(url)}")
            raise ValueError(f"URL disallowed by robots.txt: {domain}")

        # Apply rate limiting
        if self.use_rate_limiting:
            throttler.wait_if_needed(url)

        # Set headers
        headers = kwargs.pop("headers", {})
        headers["User-Agent"] = self.user_agent

        # Add proxy if available
        if self.proxies and self.proxy_validator.should_use_proxy(url):
            kwargs["proxies"] = self.proxies
            logger.debug(f"Using proxy for {sanitize_url_for_logging(url)}")

        # Fetch with retry
        try:
            logger.debug(f"Safe fetch: {method} {sanitize_url_for_logging(url)}")
            response = self._request_with_retry(
                method=method,
                url=url,
                timeout=timeout,
                headers=headers,
                **kwargs
            )
            logger.info(f"✓ Successfully fetched {sanitize_url_for_logging(url)} ({response.status_code})")
            
            # Success - remove from failed domains if present
            if domain in self.failed_domains:
                del self.failed_domains[domain]
                if hasattr(self, '_failure_counts') and domain in self._failure_counts:
                    del self._failure_counts[domain]
                logger.debug(f"Domain {domain} recovered from failure")
                    
            return response

        except (requests.Timeout, requests.ConnectTimeout) as e:
            logger.error(f"✗ Timeout fetching {sanitize_url_for_logging(url)}: {e}")
            self._record_failure(domain, is_permanent=False)
            return None

        except (requests.ConnectionError, ConnectionError) as e:
            logger.error(f"✗ Connection error fetching {sanitize_url_for_logging(url)}: {e}")
            # Connection errors might be permanent (DNS, routing issues)
            if "resolve" in str(e).lower() or "unreachable" in str(e).lower():
                self._record_failure(domain, is_permanent=True)
            else:
                self._record_failure(domain, is_permanent=False)
            return None

        except requests.HTTPError as e:
            logger.error(f"✗ HTTP error fetching {sanitize_url_for_logging(url)}: {e}")
            # 4xx errors are usually permanent (except 429)
            if hasattr(e.response, 'status_code') and 400 <= e.response.status_code < 500:
                if e.response.status_code == 429:  # Too Many Requests
                    self._record_failure(domain, is_permanent=False)
                else:
                    self._record_failure(domain, is_permanent=True)
            else:
                self._record_failure(domain, is_permanent=False)
            return None

        except requests.RequestException as e:
            logger.error(f"✗ Failed to fetch {sanitize_url_for_logging(url)}: {e}")
            self._record_failure(domain, is_permanent=False)
            return None
        except Exception as e:
            logger.error(f"✗ Unexpected error fetching {sanitize_url_for_logging(url)}: {e}")
            return None

    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        Perform safe GET request.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments

        Returns:
            Response or None
        """
        return self.fetch(url, method="GET", **kwargs)

    def post(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        Perform safe POST request.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments

        Returns:
            Response or None
        """
        return self.fetch(url, method="POST", **kwargs)

    def head(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        Perform safe HEAD request.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments

        Returns:
            Response or None
        """
        return self.fetch(url, method="HEAD", **kwargs)


# Global safe fetcher instance
_safe_fetcher = None


def get_safe_fetcher(**kwargs) -> SafeFetcher:
    """
    Get or create global safe fetcher instance.

    Args:
        **kwargs: Configuration options

    Returns:
        SafeFetcher instance
    """
    global _safe_fetcher
    if _safe_fetcher is None:
        _safe_fetcher = SafeFetcher(**kwargs)
    return _safe_fetcher


def safe_get(url: str, **kwargs) -> Optional[requests.Response]:
    """
    Perform safe GET request with global fetcher.

    Args:
        url: URL to fetch
        **kwargs: Additional arguments

    Returns:
        Response or None
    """
    fetcher = get_safe_fetcher()
    return fetcher.get(url, **kwargs)


def safe_post(url: str, **kwargs) -> Optional[requests.Response]:
    """
    Perform safe POST request with global fetcher.

    Args:
        url: URL to fetch
        **kwargs: Additional arguments

    Returns:
        Response or None
    """
    fetcher = get_safe_fetcher()
    return fetcher.post(url, **kwargs)


def configure_safe_fetcher(**kwargs):
    """
    Configure global safe fetcher.

    Args:
        **kwargs: Configuration options
    """
    global _safe_fetcher
    _safe_fetcher = SafeFetcher(**kwargs)
