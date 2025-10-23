"""Web search tool using DuckDuckGo with fallback support."""
import logging
import os
from typing import List, Dict, Optional
from ddgs import DDGS
from utils.domain_blacklist import filter_safe_urls

logger = logging.getLogger("crawllama")


def web_search(
    query: str,
    max_results: int = 3,
    region: str = "wt-wt",
    safesearch: str = "moderate"
) -> List[Dict[str, str]]:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum number of results
        region: Region code (default: worldwide)
        safesearch: Safe search level (off, moderate, strict)

    Returns:
        List of search result dictionaries with title, url, snippet
    """
    logger.info(f"Web search: '{query}'")

    try:
        results = []
        with DDGS() as ddgs:
            search_results = ddgs.text(
                query,
                max_results=max_results,
                region=region,
                safesearch=safesearch
            )

            for r in search_results:
                # Debug: Log what fields are available
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Raw search result keys: {list(r.keys())}")

                # ddgs uses 'href' for URL, 'body' for snippet
                # Old duckduckgo_search used 'link' and 'body'
                url = r.get("href") or r.get("link") or r.get("url") or ""
                title = r.get("title") or ""
                snippet = r.get("body") or r.get("snippet") or r.get("description") or ""

                if url:  # Only add if we have a URL
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet
                    })
                    logger.debug(f"✓ Added result: {title[:50]} - {url}")
                else:
                    logger.warning(f"✗ Skipping result with no URL: {title[:50]}")

        # Filter out blacklisted URLs and empty URLs
        original_count = len(results)

        # First, filter out results with empty URLs
        results_with_urls = [r for r in results if r.get("url", "").strip()]

        if len(results_with_urls) < original_count:
            logger.warning(f"Removed {original_count - len(results_with_urls)} results with empty URLs")

        # Then filter blacklisted URLs
        safe_results = [r for r in results_with_urls if r["url"] in filter_safe_urls([r["url"] for r in results_with_urls])]

        if len(safe_results) < len(results_with_urls):
            logger.warning(f"Filtered {len(results_with_urls) - len(safe_results)} blacklisted URLs")

        logger.info(f"Found {len(safe_results)} results (from {original_count} raw results)")
        return safe_results

    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return []


def web_search_news(
    query: str,
    max_results: int = 5
) -> List[Dict[str, str]]:
    """
    Search for news articles.

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of news articles
    """
    logger.info(f"News search: '{query}'")

    try:
        results = []
        with DDGS() as ddgs:
            news_results = ddgs.news(query, max_results=max_results)

            for r in news_results:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("body", ""),
                    "date": r.get("date", ""),
                    "source": r.get("source", "")
                })

        logger.info(f"Found {len(results)} news articles")
        return results

    except Exception as e:
        logger.error(f"News search failed: {e}")
        return []


def format_search_results(results: List[Dict[str, str]]) -> str:
    """
    Format search results for LLM consumption.

    Args:
        results: List of search result dictionaries

    Returns:
        Formatted string
    """
    if not results:
        return "No search results found."

    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(f"{i}. **{result['title']}**")
        formatted.append(f"   URL: {result['url']}")
        formatted.append(f"   {result['snippet']}\n")

    return "\n".join(formatted)


def brave_search(
    query: str,
    max_results: int = 3,
    api_key: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Search using Brave Search API as fallback.

    Args:
        query: Search query
        max_results: Maximum number of results
        api_key: Brave API key (or from env)

    Returns:
        List of search results
    """
    import requests

    api_key = api_key or os.getenv("BRAVE_API_KEY")
    if not api_key:
        logger.warning("Brave API key not configured")
        raise ValueError("Brave API key not configured")

    logger.info(f"Brave search: '{query}'")

    try:
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }

        params = {
            "q": query,
            "count": max_results
        }

        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        results = []

        for item in data.get("web", {}).get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", "")
            })

        # Filter blacklisted URLs
        safe_urls = filter_safe_urls([r["url"] for r in results])
        safe_results = [r for r in results if r["url"] in safe_urls]

        logger.info(f"Brave search found {len(safe_results)} results")
        return safe_results

    except Exception as e:
        logger.error(f"Brave search failed: {e}")
        raise


def serper_search(
    query: str,
    max_results: int = 3,
    api_key: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Search using Serper API as fallback.

    Args:
        query: Search query
        max_results: Maximum number of results
        api_key: Serper API key (or from env)

    Returns:
        List of search results
    """
    import requests

    api_key = api_key or os.getenv("SERPER_API_KEY")
    if not api_key:
        logger.warning("Serper API key not configured")
        raise ValueError("Serper API key not configured")

    logger.info(f"Serper search: '{query}'")

    try:
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "q": query,
            "num": max_results
        }

        response = requests.post(
            "https://google.serper.dev/search",
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        results = []

        for item in data.get("organic", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", "")
            })

        # Filter blacklisted URLs
        safe_urls = filter_safe_urls([r["url"] for r in results])
        safe_results = [r for r in results if r["url"] in safe_urls]

        logger.info(f"Serper search found {len(safe_results)} results")
        return safe_results

    except Exception as e:
        logger.error(f"Serper search failed: {e}")
        raise


def search_with_fallback(
    query: str,
    max_results: int = 3
) -> List[Dict[str, str]]:
    """
    Search with automatic fallback to alternative providers.

    Tries in order: DuckDuckGo -> Brave -> Serper

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of search results
    """
    # Try DuckDuckGo first
    try:
        results = web_search(query, max_results)
        if results:
            return results
    except Exception as e:
        logger.warning(f"DuckDuckGo failed, trying fallback: {e}")

    # Try Brave
    try:
        return brave_search(query, max_results)
    except Exception as e:
        logger.warning(f"Brave search failed, trying Serper: {e}")

    # Try Serper
    try:
        return serper_search(query, max_results)
    except Exception as e:
        logger.error(f"All search providers failed: {e}")

    return []
