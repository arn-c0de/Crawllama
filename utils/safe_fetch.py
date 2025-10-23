"""Safe fetch wrapper combining all security and reliability features."""
import requests
from typing import Optional, Dict
from utils.retry import fetch_with_retry, post_with_retry
from utils.rate_limiter import throttler
from utils.domain_blacklist import is_safe_url
from utils.proxy_validator import ProxyValidator
from utils.logger import setup_logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = setup_logger(__name__)


class SafeFetcher:
    """Secure HTTP client with all safety features enabled."""

    def __init__(
        self,
        use_rate_limiting: bool = True,
        use_blacklist: bool = True,
        use_robots: bool = True,
        use_proxy: bool = True,
        user_agent: str = "CrawlLama/1.0 (AI Research Tool)"
    ):
        """
        Initialize safe fetcher.

        Args:
            use_rate_limiting: Enable rate limiting
            use_blacklist: Enable domain blacklist
            use_robots: Respect robots.txt
            use_proxy: Use proxy if configured
            user_agent: User agent string
        """
        self.use_rate_limiting = use_rate_limiting
        self.use_blacklist = use_blacklist
        self.use_robots = use_robots
        self.use_proxy = use_proxy
        self.user_agent = user_agent

        # Load proxy configuration
        self.proxy_validator = ProxyValidator.load_from_env() if use_proxy else None
        self.proxies = self.proxy_validator.get_proxies() if self.proxy_validator else {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
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
        # Check blacklist
        if self.use_blacklist and not is_safe_url(url):
            logger.warning(f"URL blocked by blacklist: {url}")
            raise ValueError(f"URL is blacklisted: {url}")

        # Check robots.txt
        if self.use_robots and not throttler.can_fetch(url):
            logger.warning(f"URL disallowed by robots.txt: {url}")
            raise ValueError(f"URL disallowed by robots.txt: {url}")

        # Apply rate limiting
        if self.use_rate_limiting:
            throttler.wait_if_needed(url)

        # Set headers
        headers = kwargs.pop("headers", {})
        headers["User-Agent"] = self.user_agent

        # Add proxy if available
        if self.proxies and self.proxy_validator.should_use_proxy(url):
            kwargs["proxies"] = self.proxies
            logger.debug(f"Using proxy for {url}")

        # Fetch with retry
        try:
            logger.debug(f"Safe fetch: {method} {url}")
            response = self._request_with_retry(
                method=method,
                url=url,
                timeout=timeout,
                headers=headers,
                **kwargs
            )
            logger.info(f"✓ Successfully fetched {url} ({response.status_code})")
            return response

        except requests.RequestException as e:
            logger.error(f"✗ Failed to fetch {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Unexpected error fetching {url}: {e}")
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
