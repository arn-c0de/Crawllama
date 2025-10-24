"""Retry logic for network requests with tenacity.

DEPRECATED: This module is deprecated in favor of utils.safe_fetch.SafeFetcher.
The retry logic is now integrated directly into SafeFetcher.
Use get_safe_fetcher() or SafeFetcher() instead.
"""
import logging
import warnings
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger("crawllama")


def fetch_with_retry(
    url: str,
    timeout: int = 10,
    headers: Optional[Dict[str, str]] = None,
    **kwargs: Any
) -> requests.Response:
    """
    HTTP GET request with automatic retry logic.
    
    DEPRECATED: Use SafeFetcher.get() from utils.safe_fetch instead.

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
    warnings.warn(
        "fetch_with_retry() is deprecated. Use SafeFetcher from utils.safe_fetch instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from utils.safe_fetch import get_safe_fetcher
    
    fetcher = get_safe_fetcher()
    response = fetcher.get(url, timeout=timeout, headers=headers, **kwargs)
    
    if response is None:
        raise requests.RequestException(f"Failed to fetch {url} after retries")
    
    return response


def post_with_retry(
    url: str,
    json_data: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    headers: Optional[Dict[str, str]] = None,
    **kwargs: Any
) -> requests.Response:
    """
    HTTP POST request with automatic retry logic.
    
    DEPRECATED: Use SafeFetcher.post() from utils.safe_fetch instead.

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
    warnings.warn(
        "post_with_retry() is deprecated. Use SafeFetcher from utils.safe_fetch instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from utils.safe_fetch import get_safe_fetcher
    
    fetcher = get_safe_fetcher()
    response = fetcher.post(url, json=json_data, timeout=timeout, headers=headers, **kwargs)
    
    if response is None:
        raise requests.RequestException(f"Failed to POST to {url} after retries")
    
    return response

