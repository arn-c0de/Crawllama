"""Safe fetch wrapper combining all security and reliability features."""
import logging
import threading
import time
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from utils import tor_mode
from utils.domain_blacklist import is_url_not_blacklisted
from utils.logger import Logger
from utils.proxy_validator import ProxyValidator
from utils.rate_limiter import RequestThrottler
from utils.validators import (
    sanitize_exception_message,
    validate_url_ssrf_safe_pinned,
)

logger = Logger.get(__name__)

# HTTP status codes that indicate a redirect we must validate manually
REDIRECT_STATUS_CODES = (301, 302, 303, 307, 308)

# Download responses in chunks of this size to enforce the size limit
DOWNLOAD_CHUNK_SIZE = 8192


class _PinnedIPAdapter(HTTPAdapter):
    """Force every connection to a pre-validated IP address.

    SSRF validation resolves the hostname and approves its IP(s); without
    pinning, ``requests`` would re-resolve the hostname when it actually
    connects, so an attacker controlling DNS (short TTL / round-robin) can
    return a public IP for validation and an internal IP (e.g. 169.254.169.254)
    for the fetch — a DNS-rebinding SSRF.

    This adapter connects to ``pinned_ip`` while keeping the original hostname
    for TLS SNI and certificate verification (``server_hostname`` /
    ``assert_hostname``), so HTTPS verification is preserved.
    """

    def __init__(self, hostname: str, pinned_ip: str, **kwargs):
        self._hostname = hostname
        self._pinned_ip = pinned_ip
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["server_hostname"] = self._hostname
        kwargs["assert_hostname"] = self._hostname
        super().init_poolmanager(*args, **kwargs)

    def send(self, request, **kwargs):
        parsed = urlparse(request.url)
        if (parsed.hostname or "").lower() == self._hostname.lower():
            ip = f"[{self._pinned_ip}]" if ":" in self._pinned_ip else self._pinned_ip
            netloc = ip + (f":{parsed.port}" if parsed.port else "")
            request.url = urlunparse(parsed._replace(netloc=netloc))
            request.headers["Host"] = parsed.netloc
        return super().send(request, **kwargs)


class SafeFetcher:
    """Secure HTTP client with all safety features enabled."""

    def __init__(
        self,
        use_rate_limiting: bool = True,
        use_blacklist: bool = True,
        use_robots: bool = True,
        use_proxy: bool = True,
        user_agent: str = "CrawlLama/1.0 (AI Research Tool)",
        circuit_breaker_timeout: int = 300,  # 5 minutes default
        allowed_domains: set[str] | None = None,
        requests_per_second: float = 1.0,
        respect_robots: bool = True,
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
        self.allowed_domains = set(allowed_domains) if allowed_domains else None

        # Circuit breaker: track failed domains. The fetcher is shared across
        # worker threads (see AsyncFetcher), so mutations are lock-protected.
        self.failed_domains: dict[str, float] = {}  # domain -> timestamp of last failure
        self.permanent_failures: set[str] = set()  # domains that consistently fail
        self._failure_counts: dict[str, int] = {}  # domain -> consecutive failures
        self._failure_lock = threading.Lock()

        # Per-instance throttler (rate limiting + robots)
        self.throttler = RequestThrottler(
            requests_per_second=requests_per_second,
            user_agent=user_agent,
            respect_robots=respect_robots,
        )

        # Load proxy configuration
        self.proxy_validator = ProxyValidator.load_from_env() if use_proxy else None
        self.proxies = self.proxy_validator.get_proxies() if self.proxy_validator else {}

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc
    
    def _is_domain_blocked(self, domain: str) -> bool:
        """Check if domain is currently blocked by circuit breaker."""
        with self._failure_lock:
            if domain in self.permanent_failures:
                logger.debug("Domain is permanently blocked")  # lgtm[py/clear-text-logging-sensitive-data] - Domain omitted from logs
                return True

            last_failure = self.failed_domains.get(domain)
            if last_failure is None:
                return False

            remaining = self.circuit_breaker_timeout - (time.time() - last_failure)
            if remaining > 0:
                logger.debug(f"Domain blocked for another {remaining:.0f}s")  # lgtm[py/clear-text-logging-sensitive-data] - Domain omitted from logs
                return True

            # Timeout expired, remove from failed domains
            del self.failed_domains[domain]
            return False

    def _record_failure(self, domain: str, is_permanent: bool = False):
        """Record a failure for circuit breaker."""
        with self._failure_lock:
            if is_permanent:
                self.permanent_failures.add(domain)
                logger.warning("Domain marked as permanently failed")  # lgtm[py/clear-text-logging-sensitive-data] - Domain omitted from logs
                return

            current_time = time.time()
            last_failure = self.failed_domains.get(domain)
            if last_failure is not None and current_time - last_failure < self.circuit_breaker_timeout:
                # Repeated failure within the window; the 3rd becomes permanent
                self._failure_counts[domain] = self._failure_counts.get(domain, 0) + 1
                if self._failure_counts[domain] >= 3:
                    self.permanent_failures.add(domain)
                    logger.warning("Domain failed repeatedly - marked as permanent failure")  # lgtm[py/clear-text-logging-sensitive-data] - Domain omitted from logs
                    return

            self.failed_domains[domain] = current_time
            logger.debug("Domain marked as temporarily failed")  # lgtm[py/clear-text-logging-sensitive-data] - Domain omitted from logs

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
        headers: dict[str, str],
        pinned_ip: str | None = None,
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method
            url: URL to fetch
            timeout: Request timeout
            headers: HTTP headers
            pinned_ip: Pre-validated IP to connect to (anti DNS-rebinding). When
                set (and no proxy is used) the connection is forced to this IP.
            **kwargs: Additional arguments

        Returns:
            Response object

        Raises:
            requests.RequestException: If request fails
        """
        session = requests.Session()
        # Pin the connection to the validated IP, but only for direct (non-proxy)
        # requests — when a proxy/Tor is used the proxy performs resolution and
        # local IP pinning neither applies nor is desirable.
        if pinned_ip and not kwargs.get("proxies"):
            hostname = urlparse(url).hostname or ""
            adapter = _PinnedIPAdapter(hostname, pinned_ip)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
        try:
            response = session.request(method, url, timeout=timeout, headers=headers, **kwargs)
            response.raise_for_status()
        except BaseException:
            session.close()
            raise
        # Session is closed alongside the response (see _close_response_quietly).
        response._transport_session = session
        return response
    
    def _allowed_domains_list(self) -> list[str] | None:
        """Return allowed domains as a list for SSRF validation, or None."""
        return list(self.allowed_domains) if self.allowed_domains else None

    def _resolve_redirect_target(self, current_url: str, response: requests.Response) -> str | None:
        """Resolve the absolute redirect target from a redirect response.

        Returns None if the response has no Location header.
        """
        redirect_url = response.headers.get('Location')
        if not redirect_url:
            return None

        # Handle relative redirects
        return urljoin(current_url, redirect_url)

    def _assert_redirect_safe(self, redirect_url: str) -> str | None:
        """Validate a redirect target against SSRF; raise ValueError if unsafe.

        Returns the validated IP to pin the next hop's connection to (None in
        Tor mode).
        """
        is_safe, error, pinned_ip = validate_url_ssrf_safe_pinned(
            redirect_url,
            allowed_domains=self._allowed_domains_list(),
            check_dns_rebinding=True,
        )
        if not is_safe:
            logger.error("SSRF protection blocked redirect (details suppressed)")  # lgtm[py/clear-text-logging-sensitive-data] - Redirect details omitted
            raise ValueError(f"SSRF protection: Redirect to dangerous URL blocked - {sanitize_exception_message(error)}")
        return pinned_ip

    def _validate_and_follow_redirects(
        self,
        initial_url: str,
        method: str,
        timeout: int,
        headers: dict[str, str],
        max_redirects: int = 5,
        initial_pinned_ip: str | None = None,
        **kwargs
    ) -> requests.Response | None:
        """
        Manually follow redirects with SSRF validation on each hop.

        This prevents SSRF attacks via open redirects where:
        1. Initial URL is legitimate (https://trusted.com/redirect)
        2. Server redirects to dangerous URL (http://127.0.0.1/admin)
        3. Without validation, we'd follow the malicious redirect

        Args:
            initial_url: Starting URL
            method: HTTP method
            timeout: Request timeout
            headers: HTTP headers
            max_redirects: Maximum redirect hops (default: 5)
            **kwargs: Additional request arguments

        Returns:
            Final response or None if blocked

        Raises:
            ValueError: If redirect target fails SSRF validation
            requests.TooManyRedirects: If redirect chain exceeds max_redirects
        """
        current_url = initial_url
        current_pinned_ip = initial_pinned_ip
        redirect_count = 0

        # Disable automatic redirects - we'll handle them manually
        kwargs['allow_redirects'] = False

        while redirect_count < max_redirects:
            # Make request without following redirects, pinned to the validated IP
            response = self._request_with_retry(
                method=method,
                url=current_url,
                timeout=timeout,
                headers=headers,
                pinned_ip=current_pinned_ip,
                **kwargs
            )

            # If response is None (failed), return None
            if response is None:
                return None

            # Not a redirect, return the response
            if response.status_code not in REDIRECT_STATUS_CODES:
                return response

            redirect_url = self._resolve_redirect_target(current_url, response)
            if redirect_url is None:
                logger.warning("Redirect without Location header")  # lgtm[py/clear-text-logging-sensitive-data] - Redirect target omitted to avoid logging URL
                return response  # Return as-is

            logger.info(f"Following redirect {redirect_count + 1}")  # lgtm[py/clear-text-logging-sensitive-data] - Redirect details omitted to avoid logging URLs

            # Release this hop's connection/session before the next request
            self._close_response_quietly(response)

            # SECURITY: Validate redirect target against SSRF and pin its IP
            current_pinned_ip = self._assert_redirect_safe(redirect_url)

            # Update for next iteration
            current_url = redirect_url
            redirect_count += 1

            # For 303, change method to GET
            if response.status_code == 303 and method != 'GET':
                method = 'GET'
                # Remove body for GET requests
                kwargs.pop('data', None)
                kwargs.pop('json', None)

        # Too many redirects
        logger.warning(f"Exceeded max redirects ({max_redirects})")  # lgtm[py/clear-text-logging-sensitive-data] - Initial URL omitted to avoid logging URLs
        raise requests.TooManyRedirects(f"Exceeded {max_redirects} redirects")

    def _enforce_pre_fetch_policies(self, url: str) -> tuple[str, str | None]:
        """Run all pre-request security checks; return (domain, pinned_ip).

        Checks (in order): SSRF validation, circuit breaker, blacklist, robots.txt.
        ``pinned_ip`` is the validated IP the fetch must connect to (None in Tor
        mode).

        Raises:
            ValueError: If any check blocks the URL
        """
        # SSRF Protection: Validate URL before any network operations
        is_safe, ssrf_error, pinned_ip = validate_url_ssrf_safe_pinned(
            url,
            allowed_domains=self._allowed_domains_list(),
            check_dns_rebinding=True,
        )
        if not is_safe:
            logger.error("SSRF protection blocked request")
            raise ValueError(f"SSRF protection: {ssrf_error}")

        domain = self._get_domain(url)

        # Check circuit breaker first
        if self._is_domain_blocked(domain):
            logger.warning("URL blocked by circuit breaker")  # lgtm[py/clear-text-logging-sensitive-data] - URL content not logged
            raise ValueError("Domain temporarily unavailable")

        # Check blacklist
        if self.use_blacklist and not is_url_not_blacklisted(url):
            logger.warning("URL blocked by blacklist")  # lgtm[py/clear-text-logging-sensitive-data] - URL content not logged
            raise ValueError("URL is blacklisted")

        # Check robots.txt
        if self.use_robots and not self.throttler.can_fetch(url):
            logger.warning("URL disallowed by robots.txt")  # lgtm[py/clear-text-logging-sensitive-data] - URL content not logged
            raise ValueError("URL disallowed by robots.txt")

        return domain, pinned_ip

    def _prepare_headers_and_proxy(self, url: str, kwargs: dict) -> dict[str, str]:
        """Build request headers and add proxy settings to kwargs if needed."""
        headers = kwargs.pop("headers", {})
        headers["User-Agent"] = self.user_agent

        # Tor mode takes precedence over any user-configured proxy: every
        # request must go through Tor, regardless of when this fetcher
        # instance was created.
        tor_proxies = tor_mode.requests_proxies()
        if tor_proxies:
            kwargs["proxies"] = tor_proxies
            logger.debug("Routing request through Tor")
        elif self.proxies and self.proxy_validator.should_use_proxy(url):
            kwargs["proxies"] = self.proxies
            logger.debug("Using proxy for URL")  # lgtm[py/clear-text-logging-sensitive-data] - URL content not logged

        return headers

    def _send_request(
        self,
        url: str,
        method: str,
        timeout: int,
        headers: dict[str, str],
        allow_redirects: bool,
        max_redirects: int,
        pinned_ip: str | None = None,
        **kwargs
    ) -> requests.Response | None:
        """Send the request, with manual redirect validation when redirects are allowed."""
        if allow_redirects:
            # Use manual redirect validation to prevent SSRF via open redirects
            return self._validate_and_follow_redirects(
                initial_url=url,
                method=method,
                timeout=timeout,
                headers=headers,
                max_redirects=max_redirects,
                initial_pinned_ip=pinned_ip,
                **kwargs
            )

        # Disable redirects entirely
        kwargs['allow_redirects'] = False
        return self._request_with_retry(
            method=method,
            url=url,
            timeout=timeout,
            headers=headers,
            pinned_ip=pinned_ip,
            **kwargs
        )

    def _check_content_length_header(self, response: requests.Response, max_size_mb: int) -> None:
        """SECURITY: Check Content-Length header before downloading.

        Raises:
            ValueError: If the declared size exceeds the limit
        """
        content_length = response.headers.get('Content-Length')
        if not content_length:
            return

        max_size_bytes = max_size_mb * 1024 * 1024
        try:
            size_bytes = int(content_length)
            if size_bytes > max_size_bytes:
                size_mb = size_bytes / (1024 * 1024)
                logger.error(
                    f"Response too large: {size_mb:.2f}MB exceeds limit of {max_size_mb}MB"
                )  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted to avoid logging URLs
                raise ValueError(
                    f"Response size ({size_mb:.2f}MB) exceeds maximum allowed size ({max_size_mb}MB). "
                    f"This prevents memory exhaustion attacks."
                )
        except ValueError as ve:
            if "exceeds maximum" in str(ve):
                raise  # Re-raise our custom error
            # Invalid Content-Length header - continue with streaming check
            # lgtm[py/clear-text-logging-sensitive-data] - Not logging content length to avoid false positive
            logger.warning("Invalid Content-Length header detected")

    def _download_with_size_limit(self, response: requests.Response, max_size_mb: int) -> float:
        """SECURITY: Download response content with a hard size limit.

        Enforces the limit even if the Content-Length header is missing or wrong.
        Sets response._content to the downloaded bytes.

        Returns:
            Downloaded size in MB

        Raises:
            ValueError: If the download exceeds the size limit
        """
        max_size_bytes = max_size_mb * 1024 * 1024
        downloaded_bytes = 0
        content_chunks = []

        try:
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                if not chunk:  # filter out keep-alive new chunks
                    continue

                downloaded_bytes += len(chunk)

                # Check if we've exceeded the limit
                if downloaded_bytes > max_size_bytes:
                    downloaded_mb = downloaded_bytes / (1024 * 1024)
                    logger.error(  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted to avoid logging URLs
                        f"Response exceeded size limit during download: {downloaded_mb:.2f}MB > {max_size_mb}MB"
                    )
                    raise ValueError(
                        f"Response exceeded {max_size_mb}MB during download. "
                        f"Downloaded {downloaded_mb:.2f}MB before stopping. "
                        f"This prevents memory exhaustion attacks."
                    )

                content_chunks.append(chunk)

        except requests.exceptions.ChunkedEncodingError as e:
            logger.warning(f"Chunked encoding error (continuing with partial content): {e}")
            # Continue with partial content - common with interrupted streams

        # Reconstruct response content
        response._content = b''.join(content_chunks)
        return downloaded_bytes / (1024 * 1024)

    def _clear_failure_state(self, domain: str) -> None:
        """Remove domain from failure tracking after a successful fetch."""
        with self._failure_lock:
            if domain not in self.failed_domains:
                return
            del self.failed_domains[domain]
            self._failure_counts.pop(domain, None)
        logger.debug("Domain recovered from failure state")

    def _handle_connection_error(self, domain: str, error: Exception) -> None:
        """Record a connection failure, permanent for DNS/routing issues."""
        logger.error("✗ Connection error fetching URL")
        # Connection errors might be permanent (DNS, routing issues)
        error_msg = str(error).lower()
        is_permanent = "resolve" in error_msg or "unreachable" in error_msg
        self._record_failure(domain, is_permanent=is_permanent)

    def _handle_http_error(self, domain: str, error: requests.HTTPError) -> None:
        """Record an HTTP failure; 4xx errors are usually permanent (except 429)."""
        logger.error("✗ HTTP error fetching URL")
        if hasattr(error.response, 'status_code') and 400 <= error.response.status_code < 500:
            # 429 Too Many Requests is temporary, other 4xx are permanent
            self._record_failure(domain, is_permanent=error.response.status_code != 429)
        else:
            self._record_failure(domain, is_permanent=False)

    def _close_response_quietly(self, response: requests.Response | None) -> None:
        """Close the response (and any pinned session), logging close errors."""
        if response is None:
            return
        try:
            response.close()
        except requests.RequestException as close_error:
            logger.debug(f"Response close failed: {sanitize_exception_message(str(close_error))}")
        # Close the per-request transport session, if any.
        session = getattr(response, "_transport_session", None)
        if session is not None:
            try:
                session.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass

    def fetch(
        self,
        url: str,
        method: str = "GET",
        timeout: int = 10,
        max_size_mb: int = 50,
        allow_redirects: bool = True,
        max_redirects: int = 5,
        **kwargs
    ) -> requests.Response | None:
        """
        Safely fetch a URL with all security features.

        Args:
            url: URL to fetch
            method: HTTP method
            timeout: Request timeout
            max_size_mb: Maximum response size in MB (default: 50MB, prevents DoS)
            **kwargs: Additional arguments for requests

        Returns:
            Response object or None if failed/blocked

        Raises:
            ValueError: If URL is blocked by security checks or response too large
        """
        domain, pinned_ip = self._enforce_pre_fetch_policies(url)

        # Apply rate limiting
        if self.use_rate_limiting:
            self.throttler.wait_if_needed(url)

        headers = self._prepare_headers_and_proxy(url, kwargs)

        # Fetch with retry
        response = None
        try:
            logger.debug(f"Safe fetch: {method}")  # lgtm[py/clear-text-logging-sensitive-data] - URL not logged to avoid leaking info

            # Enable streaming to handle large responses safely
            kwargs['stream'] = True

            response = self._send_request(
                url, method, timeout, headers, allow_redirects, max_redirects,
                pinned_ip=pinned_ip, **kwargs
            )
            if response is None:
                logger.error("✗ No response received from fetch")
                return None

            self._check_content_length_header(response, max_size_mb)
            downloaded_mb = self._download_with_size_limit(response, max_size_mb)

            logger.info(  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted to avoid logging URLs
                f"✓ Successfully fetched (status={response.status_code}, {downloaded_mb:.2f}MB)"
            )

            # Success - remove from failed domains if present
            self._clear_failure_state(domain)
            return response

        except ValueError:
            # ValueError from SSRF protection - re-raise it
            logger.error("✗ Security validation failed")
            raise  # Re-raise the ValueError

        except requests.TooManyRedirects:
            # Redirect loop detected - re-raise
            logger.error("✗ Too many redirects")
            raise  # Re-raise the exception

        except (requests.Timeout, requests.ConnectTimeout):
            logger.error("✗ Timeout fetching URL")
            self._record_failure(domain, is_permanent=False)
            return None

        except (requests.ConnectionError, ConnectionError) as e:
            self._handle_connection_error(domain, e)
            return None

        except requests.HTTPError as e:
            self._handle_http_error(domain, e)
            return None

        except requests.RequestException as e:
            sanitized_error = sanitize_exception_message(str(e))
            logger.error(f"✗ Failed to fetch URL: {sanitized_error}")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted to avoid logging URLs
            self._record_failure(domain, is_permanent=False)
            return None
        except Exception as e:
            sanitized_error = sanitize_exception_message(str(e))
            logger.error(f"✗ Unexpected error fetching URL: {sanitized_error}")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted from logs
            return None
        finally:
            self._close_response_quietly(response)

    def get(self, url: str, **kwargs) -> requests.Response | None:
        """
        Perform safe GET request.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments

        Returns:
            Response or None
        """
        return self.fetch(url, method="GET", **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response | None:
        """
        Perform safe POST request.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments

        Returns:
            Response or None
        """
        return self.fetch(url, method="POST", **kwargs)

    def head(self, url: str, **kwargs) -> requests.Response | None:
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


def safe_get(url: str, **kwargs) -> requests.Response | None:
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


def safe_post(url: str, **kwargs) -> requests.Response | None:
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
