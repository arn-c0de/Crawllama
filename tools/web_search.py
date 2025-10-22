"""Web search tool using DuckDuckGo with fallback support."""
import logging
from typing import List, Dict, Optional
from duckduckgo_search import DDGS

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
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "snippet": r.get("body", "")
                })

        logger.info(f"Found {len(results)} results")
        return results

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
