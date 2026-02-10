"""Proxy validation and management for web requests."""
import os
import requests
from typing import Dict, Optional, List
from urllib.parse import urlparse
from utils.logger import setup_logger

logger = setup_logger(__name__)

def _redact_proxy_url(proxy_url: str) -> str:
    """Redact credentials in proxy URLs for safe logging."""
    try:
        parsed = urlparse(proxy_url)
        if parsed.username or parsed.password:
            return f"{parsed.scheme}://***:***@{parsed.hostname}:{parsed.port}"
        return proxy_url
    except Exception:
        return "[invalid proxy url]"


class ProxyValidator:
    """Validate and manage proxy configurations."""

    def __init__(self):
        """Initialize proxy validator."""
        self.proxies: Dict[str, Optional[str]] = {}
        self.validated = False

    @classmethod
    def load_from_env(cls) -> "ProxyValidator":
        """
        Load proxy configuration from environment variables.

        Environment variables:
            HTTP_PROXY: HTTP proxy URL
            HTTPS_PROXY: HTTPS proxy URL
            NO_PROXY: Comma-separated list of hosts to bypass proxy

        Returns:
            ProxyValidator instance
        """
        validator = cls()
        validator.proxies = {
            "http": os.getenv("HTTP_PROXY"),
            "https": os.getenv("HTTPS_PROXY")
        }
        return validator

    def validate_proxies(self, test_urls: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        Validate proxy connections.

        Args:
            test_urls: List of URLs to test proxy with (defaults to common test URLs)

        Returns:
            Dictionary with proxy types and validation status
        """
        if test_urls is None:
            test_urls = [
                "https://www.google.com",
                "https://www.cloudflare.com"
            ]

        results = {}

        for proxy_type, proxy_url in self.proxies.items():
            if not proxy_url:
                results[proxy_type] = True  # No proxy configured is valid
                continue

            try:
                # Test proxy with a simple request
                logger.info(f"Testing {proxy_type} proxy: {_redact_proxy_url(proxy_url)}")

                proxies = {proxy_type: proxy_url}
                response = requests.get(
                    test_urls[0],
                    proxies=proxies,
                    timeout=10,
                    headers={"User-Agent": "CrawlLama/1.0 Proxy-Validator"}
                )

                if response.status_code < 500:
                    results[proxy_type] = True
                    logger.info(f"✓ {proxy_type} proxy is valid")
                else:
                    results[proxy_type] = False
                    logger.warning(f"✗ {proxy_type} proxy returned {response.status_code}")

            except requests.exceptions.ProxyError as e:
                results[proxy_type] = False
                logger.error(f"✗ {proxy_type} proxy error: {e}")

            except requests.exceptions.Timeout:
                results[proxy_type] = False
                logger.error(f"✗ {proxy_type} proxy timeout")

            except Exception as e:
                results[proxy_type] = False
                logger.error(f"✗ {proxy_type} proxy validation failed: {e}")

        self.validated = True
        return results

    def get_proxies(self) -> Dict[str, Optional[str]]:
        """
        Get proxy configuration for requests.

        Returns:
            Dictionary with proxy configuration
        """
        # Filter out None values
        return {k: v for k, v in self.proxies.items() if v is not None}

    def is_configured(self) -> bool:
        """
        Check if any proxy is configured.

        Returns:
            True if at least one proxy is configured
        """
        return any(self.proxies.values())

    @staticmethod
    def parse_proxy_url(proxy_url: str) -> Dict[str, str]:
        """
        Parse proxy URL and extract components.

        Args:
            proxy_url: Proxy URL (e.g., "http://user:pass@proxy.com:8080")

        Returns:
            Dictionary with proxy components
        """
        parsed = urlparse(proxy_url)
        return {
            "scheme": parsed.scheme,
            "hostname": parsed.hostname,
            "port": parsed.port,
            "username": parsed.username,
            "password": parsed.password
        }

    def get_no_proxy_list(self) -> List[str]:
        """
        Get list of hosts that should bypass proxy.

        Returns:
            List of hostnames/patterns
        """
        no_proxy = os.getenv("NO_PROXY", "")
        if not no_proxy:
            return []

        return [host.strip() for host in no_proxy.split(",")]

    def should_use_proxy(self, url: str) -> bool:
        """
        Check if a URL should use proxy.

        Args:
            url: URL to check

        Returns:
            True if proxy should be used
        """
        if not self.is_configured():
            return False

        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return False

        # Check NO_PROXY list
        no_proxy_list = self.get_no_proxy_list()
        for pattern in no_proxy_list:
            if pattern.startswith("."):
                # Domain suffix match
                if hostname.endswith(pattern[1:]) or hostname == pattern[1:]:
                    return False
            elif pattern == hostname:
                return False

        return True


def get_proxy_config() -> Dict[str, Optional[str]]:
    """
    Get validated proxy configuration.

    Returns:
        Dictionary with proxy configuration
    """
    validator = ProxyValidator.load_from_env()

    if validator.is_configured():
        results = validator.validate_proxies()
        if all(results.values()):
            logger.info("All proxies validated successfully")
            return validator.get_proxies()
        else:
            logger.warning("Some proxies failed validation, proceeding without proxy")
            return {}

    return {}
