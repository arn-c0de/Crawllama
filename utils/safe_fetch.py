"""Safe fetch wrapper combining all security and reliability features."""
import logging
import re
import requests
import time
from typing import Optional, Dict, Set
from utils.rate_limiter import RequestThrottler
from utils.domain_blacklist import is_url_not_blacklisted
from utils.proxy_validator import ProxyValidator
from utils.logger import setup_logger
from utils.validators import sanitize_url_for_logging, validate_url_ssrf_safe, sanitize_for_logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

logger = setup_logger(__name__)


def sanitize_exception_message(exception_msg: str) -> str:
    """
    Sanitize exception messages to remove sensitive URLs.
    
    Replaces URLs in exception messages with sanitized versions.
    
    Args:
        exception_msg: Raw exception message
        
    Returns:
        Sanitized message with URLs redacted
    """
    # Pattern to match URLs in exception messages
    url_pattern = r'https?://[^\s<>"\']+'
    
    def replace_url(match):
        url = match.group(0)
        return sanitize_url_for_logging(url)
    
    return re.sub(url_pattern, replace_url, exception_msg)


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
        allowed_domains: Optional[Set[str]] = None,
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

        # Circuit breaker: track failed domains
        self.failed_domains: Dict[str, float] = {}  # domain -> timestamp of last failure
        self.permanent_failures: Set[str] = set()  # domains that consistently fail

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
        from urllib.parse import urlparse
        return urlparse(url).netloc
    
    def _is_domain_blocked(self, domain: str) -> bool:
        """Check if domain is currently blocked by circuit breaker."""
        current_time = time.time()
        
        # Check permanent failures
        if domain in self.permanent_failures:
            logger.debug("Domain is permanently blocked")  # lgtm[py/clear-text-logging-sensitive-data] - Domain omitted from logs
            return True
        
        # Check temporary failures
        if domain in self.failed_domains:
            last_failure = self.failed_domains[domain]
            if current_time - last_failure < self.circuit_breaker_timeout:
                remaining = self.circuit_breaker_timeout - (current_time - last_failure)
                logger.debug("Domain blocked for remaining timeout")  # lgtm[py/clear-text-logging-sensitive-data] - Domain omitted from logs
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
            logger.warning("Domain marked as permanently failed")  # lgtm[py/clear-text-logging-sensitive-data] - Domain omitted from logs
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
    
    def _validate_and_follow_redirects(
        self,
        initial_url: str,
        method: str,
        timeout: int,
        headers: Dict[str, str],
        max_redirects: int = 5,
        **kwargs
    ) -> Optional[requests.Response]:
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
        redirect_count = 0
        
        # Disable automatic redirects - we'll handle them manually
        kwargs['allow_redirects'] = False
        
        while redirect_count < max_redirects:
            # Make request without following redirects
            response = self._request_with_retry(
                method=method,
                url=current_url,
                timeout=timeout,
                headers=headers,
                **kwargs
            )
            
            # If response is None (failed), return None
            if response is None:
                return None
            
            # Check if it's a redirect status
            if response.status_code not in [301, 302, 303, 307, 308]:
                # Not a redirect, return the response
                return response
            
            # Get redirect target
            redirect_url = response.headers.get('Location')
            if not redirect_url:
                logger.warning("Redirect without Location header")  # lgtm[py/clear-text-logging-sensitive-data] - Redirect target omitted to avoid logging URL
                return response  # Return as-is
            
            # Handle relative redirects
            from urllib.parse import urljoin
            redirect_url = urljoin(current_url, redirect_url)
            
            logger.info(f"Following redirect {redirect_count + 1}")  # lgtm[py/clear-text-logging-sensitive-data] - Redirect details omitted to avoid logging URLs
            
            # SECURITY: Validate redirect target against SSRF
            is_safe, error = validate_url_ssrf_safe(
                redirect_url,
                allowed_domains=list(self.allowed_domains) if self.allowed_domains else None,
                check_dns_rebinding=True,
            )
            if not is_safe:
                logger.error("SSRF protection blocked redirect (details suppressed)")  # lgtm[py/clear-text-logging-sensitive-data] - Redirect details omitted
                raise ValueError(f"SSRF protection: Redirect to dangerous URL blocked - {sanitize_exception_message(error)}")
            
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

    def fetch(
        self,
        url: str,
        method: str = "GET",
        timeout: int = 10,
        max_size_mb: int = 50,
        allow_redirects: bool = True,
        max_redirects: int = 5,
        **kwargs
    ) -> Optional[requests.Response]:
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
        # SSRF Protection: Validate URL before any network operations
        is_safe, ssrf_error = validate_url_ssrf_safe(
            url,
            allowed_domains=list(self.allowed_domains) if self.allowed_domains else None,
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

        # Apply rate limiting
        if self.use_rate_limiting:
            self.throttler.wait_if_needed(url)

        # Set headers
        headers = kwargs.pop("headers", {})
        headers["User-Agent"] = self.user_agent

        # Add proxy if available
        if self.proxies and self.proxy_validator.should_use_proxy(url):
            kwargs["proxies"] = self.proxies
            logger.debug("Using proxy for URL")  # lgtm[py/clear-text-logging-sensitive-data] - URL content not logged

        # Fetch with retry
        response = None
        try:
            logger.debug(f"Safe fetch: {method}")  # lgtm[py/clear-text-logging-sensitive-data] - URL not logged to avoid leaking info

            # Enable streaming to handle large responses safely
            kwargs['stream'] = True

            if allow_redirects:
                # Use manual redirect validation to prevent SSRF via open redirects
                response = self._validate_and_follow_redirects(
                    initial_url=url,
                    method=method,
                    timeout=timeout,
                    headers=headers,
                    max_redirects=max_redirects,
                    **kwargs
                )
            else:
                # Disable redirects entirely
                kwargs['allow_redirects'] = False
                response = self._request_with_retry(
                    method=method,
                    url=url,
                    timeout=timeout,
                    headers=headers,
                    **kwargs
                )

            if response is None:
                logger.error("✗ No response received from fetch")
                return None

            # SECURITY: Check Content-Length header before downloading
            content_length = response.headers.get('Content-Length')
            max_size_bytes = max_size_mb * 1024 * 1024

            if content_length:
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

            # SECURITY: Download with size limit (even if Content-Length missing/wrong)
            downloaded_bytes = 0
            content_chunks = []

            try:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive new chunks
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
            downloaded_mb = downloaded_bytes / (1024 * 1024)

            logger.info(  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted to avoid logging URLs
                f"✓ Successfully fetched (status={response.status_code}, {downloaded_mb:.2f}MB)"
            )

            # Success - remove from failed domains if present
            if domain in self.failed_domains:
                del self.failed_domains[domain]
                if hasattr(self, '_failure_counts') and domain in self._failure_counts:
                    del self._failure_counts[domain]
                logger.debug("Domain recovered from failure state")

            return response

        except ValueError as e:
            # ValueError from SSRF protection - re-raise it
            logger.error("✗ Security validation failed")
            raise  # Re-raise the ValueError

        except requests.TooManyRedirects as e:
            # Redirect loop detected - re-raise
            logger.error("✗ Too many redirects")
            raise  # Re-raise the exception

        except (requests.Timeout, requests.ConnectTimeout) as e:
            logger.error("✗ Timeout fetching URL")
            self._record_failure(domain, is_permanent=False)
            return None

        except (requests.ConnectionError, ConnectionError) as e:
            logger.error("✗ Connection error fetching URL")
            # Connection errors might be permanent (DNS, routing issues)
            error_msg = str(e).lower()
            if "resolve" in error_msg or "unreachable" in error_msg:
                self._record_failure(domain, is_permanent=True)
            else:
                self._record_failure(domain, is_permanent=False)
            return None

        except requests.HTTPError as e:
            logger.error("✗ HTTP error fetching URL")
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
            sanitized_error = sanitize_exception_message(str(e))
            logger.error(f"✗ Failed to fetch URL: {sanitized_error}")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted to avoid logging URLs
            self._record_failure(domain, is_permanent=False)
            return None
        except Exception as e:
            sanitized_error = sanitize_exception_message(str(e))
            logger.error(f"✗ Unexpected error fetching URL: {sanitized_error}")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted from logs
            return None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass

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
