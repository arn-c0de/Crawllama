"""Retry logic for network requests with tenacity."""
import logging
import requests
from typing import Optional, Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger("crawllama")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def fetch_with_retry(
    url: str,
    timeout: int = 10,
    headers: Optional[Dict[str, str]] = None,
    **kwargs: Any
) -> requests.Response:
    """
    HTTP GET request with automatic retry logic.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        headers: Optional HTTP headers
        **kwargs: Additional requests arguments

    Returns:
        Response object

    Raises:
        requests.RequestException: After all retries exhausted
    """
    if headers is None:
        headers = {
            "User-Agent": "CrawlLama/1.0 (Educational Research Bot; +https://github.com/crawllama)"
        }

    try:
        response = requests.get(url, timeout=timeout, headers=headers, **kwargs)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        logger.error(f"Request failed: {url} - {e}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def post_with_retry(
    url: str,
    json_data: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    headers: Optional[Dict[str, str]] = None,
    **kwargs: Any
) -> requests.Response:
    """
    HTTP POST request with automatic retry logic.

    Args:
        url: URL to post to
        json_data: JSON data to send
        timeout: Request timeout in seconds
        headers: Optional HTTP headers
        **kwargs: Additional requests arguments

    Returns:
        Response object

    Raises:
        requests.RequestException: After all retries exhausted
    """
    if headers is None:
        headers = {
            "User-Agent": "CrawlLama/1.0",
            "Content-Type": "application/json"
        }

    try:
        response = requests.post(url, json=json_data, timeout=timeout, headers=headers, **kwargs)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        logger.error(f"POST request failed: {url} - {e}")
        raise
