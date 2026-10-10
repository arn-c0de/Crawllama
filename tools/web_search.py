"""Web search tool using DuckDuckGo with fallback support."""
import html
import logging
import os
import re
import time
from urllib.parse import urlparse

from ddgs import DDGS

from tools.page_reader import filter_prompt_injection
from tools.search_ranking import (
    rerank_results,
    resolve_ranking_profile,
    resolve_search_preferences,
)
from utils import tor_mode
from utils.domain_blacklist import filter_safe_urls
from utils.validators import sanitize_for_logging

logger = logging.getLogger("crawllama")


def _sanitize_text_fragment(text: str, max_chars: int = 320) -> str:
    """Remove HTML artifacts and normalize short text fragments (titles/snippets).

    SECURITY: search snippets/titles are attacker-influenceable (SEO, poisoned
    indexes) and flow straight into the LLM prompt, so they receive the same
    prompt-injection filtering as full page reads.
    """
    if not text:
        return ""

    cleaned = html.unescape(str(text))
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)  # strip HTML tags
    cleaned = cleaned.replace("\x00", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Remove obvious raw markup leftovers
    cleaned = re.sub(r"(?:&lt;|&gt;|<|>){2,}", " ", cleaned).strip()

    # Strip prompt-injection payloads (decodes obfuscation, filters patterns).
    cleaned = filter_prompt_injection(cleaned)

    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(" ", 1)[0].strip() + "..."
    return cleaned


def _safe_search_result(title: str, url: str, snippet: str, **extra: str) -> dict[str, str]:
    """Build a normalized result dict from provider-specific fields."""
    result = {
        "title": _sanitize_text_fragment(title, max_chars=180),
        "url": url or "",
        "snippet": _sanitize_text_fragment(snippet, max_chars=320),
    }
    result.update(extra)
    return result


def _filter_safe_results(results: list[dict[str, str]]) -> list[dict[str, str]]:
    """Drop empty and blacklisted URLs while preserving result order."""
    results_with_urls = [result for result in results if result.get("url", "").strip()]
    removed_empty = len(results) - len(results_with_urls)
    if removed_empty:
        logger.warning(f"Removed {removed_empty} results with empty URLs")

    safe_urls = set(filter_safe_urls([result["url"] for result in results_with_urls]))
    safe_results = [result for result in results_with_urls if result["url"] in safe_urls]
    filtered_count = len(results_with_urls) - len(safe_results)
    if filtered_count:
        logger.warning(f"Filtered {filtered_count} blacklisted URLs")

    return safe_results


def _extract_domain_candidates(query: str, region: str) -> list[str]:
    """Extract likely domain candidates from a query for supplemental site-specific lookups."""
    lowered_query = (query or "").lower()
    if not lowered_query or "site:" in lowered_query:
        return []

    explicit_domains = re.findall(r"\b[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.[a-z]{2,}\b", lowered_query)
    if explicit_domains:
        deduped: list[str] = []
        for domain in explicit_domains:
            if domain not in deduped:
                deduped.append(domain)
        return deduped[:2]

    tld = ".de" if (region or "").lower().startswith("de-") else ".com"
    brand_tokens = re.findall(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", lowered_query)
    candidates: list[str] = []
    for token in brand_tokens:
        if len(token) < 4:
            continue
        domain = f"{token}{tld}"
        if domain not in candidates:
            candidates.append(domain)
    return candidates[:2]


def _host_matches_domain(url: str, domain: str) -> bool:
    """Check if URL host matches domain (exact or subdomain)."""
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except Exception:
        return False
    normalized_domain = (domain or "").lower().rstrip(".")
    if not host or not normalized_domain:
        return False
    return host == normalized_domain or host.endswith(f".{normalized_domain}")


def _merge_unique_results(
    primary: list[dict[str, str]],
    secondary: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Merge search results without duplicate URLs."""
    merged: list[dict[str, str]] = []
    seen_urls = set()

    for bucket in (primary, secondary):
        for item in bucket:
            url = (item.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            merged.append(item)

    return merged


def _promote_domain_matches(
    results: list[dict[str, str]],
    domains: list[str],
    max_promoted_per_domain: int = 1,
) -> list[dict[str, str]]:
    """Move domain-matching results to the front so they appear in source references."""
    if not results or not domains:
        return results

    promoted: list[dict[str, str]] = []
    remaining: list[dict[str, str]] = []
    promoted_urls = set()

    for domain in domains:
        promoted_count = 0
        for result in results:
            url = (result.get("url") or "").strip()
            if not url or url in promoted_urls:
                continue
            if _host_matches_domain(url, domain):
                promoted.append(result)
                promoted_urls.add(url)
                promoted_count += 1
                if promoted_count >= max_promoted_per_domain:
                    break

    for result in results:
        url = (result.get("url") or "").strip()
        if not url or url in promoted_urls:
            continue
        remaining.append(result)

    return promoted + remaining


def _ddgs_with_retry(work, label: str, max_retries: int = 2, retry_delay: float = 1.0):
    """Run a DDGS operation with exponential-backoff retries.

    ``work`` is a zero-arg callable that performs the search and returns a list
    of result dicts. Returns that list, or ``None`` if every attempt failed.
    """
    delay = retry_delay
    for attempt in range(max_retries + 1):
        try:
            return work()
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.warning(f"DDGS {label} connection error on attempt {attempt + 1}/{max_retries + 1}: {e}")
        except Exception as e:
            logger.error(f"DDGS {label} failed with unexpected error: {e}")
        if attempt < max_retries:
            logger.info(f"Retrying {label} in {delay}s...")
            time.sleep(delay)
            delay *= 2  # Exponential backoff
        else:
            logger.error(f"All DDGS {label} retry attempts failed")
    return None


def _collect_text_results(
    query: str,
    max_results: int,
    region: str,
    safesearch: str,
) -> list[dict[str, str]]:
    """Run a DDGS text search and normalize the raw results."""
    collected = []
    with DDGS(proxy=tor_mode.ddgs_proxy()) as ddgs:
        search_results = ddgs.text(
            query,
            max_results=max_results,
            region=region,
            safesearch=safesearch
        )

        for r in search_results:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Raw search result keys: {list(r.keys())}")

            # ddgs uses 'href' for URL, 'body' for snippet
            # Old duckduckgo_search used 'link' and 'body'
            url = r.get("href") or r.get("link") or r.get("url") or ""
            title = r.get("title") or ""

            if url:  # Only add if we have a URL
                collected.append(_safe_search_result(
                    title=title,
                    url=url,
                    snippet=r.get("body") or r.get("snippet") or r.get("description") or "",
                ))
                logger.debug(f"✓ Added result: {title[:50]} - {url}")
            else:
                logger.warning(f"✗ Skipping result with no URL: {title[:50]}")
    return collected


def web_search(
    query: str,
    max_results: int = 3,
    region: str = "de-de",
    safesearch: str = "moderate",
    ranking_profile: str = "balanced",
) -> list[dict[str, str]]:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum number of results
        region: Region code (default: de-de, should be passed from config)
        safesearch: Safe search level (off, moderate, strict)

    Returns:
        List of search result dictionaries with title, url, snippet
    """
    cleaned_query, effective_region = resolve_search_preferences(query, default_region=region)
    effective_profile = resolve_ranking_profile(cleaned_query, ranking_profile)
    if not cleaned_query:
        logger.warning("Web search skipped because cleaned query is empty")
        return []

    safe_query = sanitize_for_logging(cleaned_query)
    logger.info(f"Web search: '{safe_query}'")
    logger.info(
        "Search preferences resolved | profile=%s | region=%s",
        effective_profile,
        effective_region,
    )

    try:
        results = _ddgs_with_retry(
            lambda: _collect_text_results(cleaned_query, max_results, effective_region, safesearch),
            "search",
        )
        if results is None:
            return []

        original_count = len(results)
        safe_results = _filter_safe_results(results)

        reranked_results = rerank_results(cleaned_query, safe_results, ranking_profile=effective_profile)
        logger.info(f"Found {len(reranked_results)} results (from {original_count} raw results)")
        
        # Log if DuckDuckGo returned fewer results than requested
        if len(reranked_results) < max_results:
            logger.warning(f"DuckDuckGo returned only {len(reranked_results)} results (requested: {max_results}). This is a known limitation.")
        
        return reranked_results

    except Exception as e:
        logger.error(f"Web search failed with critical error: {e}")
        return []


def web_search_news(
    query: str,
    max_results: int = 5
) -> list[dict[str, str]]:
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
        def _do_news_search():
            collected = []
            with DDGS(proxy=tor_mode.ddgs_proxy()) as ddgs:
                news_results = ddgs.news(query, max_results=max_results)
                for r in news_results:
                    collected.append(_safe_search_result(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=r.get("body", ""),
                        date=r.get("date", ""),
                        source=r.get("source", ""),
                    ))
            return collected

        results = _ddgs_with_retry(_do_news_search, "news search")
        if results is None:
            return []

        logger.info(f"Found {len(results)} news articles")
        return results

    except Exception as e:
        logger.error(f"News search failed with critical error: {e}")
        return []


def format_search_results(results: list[dict[str, str]]) -> str:
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
    api_key: str | None = None,
    ranking_profile: str = "balanced",
) -> list[dict[str, str]]:
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
    effective_profile = resolve_ranking_profile(query, ranking_profile)
    logger.info("Brave ranking profile resolved | profile=%s", effective_profile)

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
            results.append(_safe_search_result(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
            ))

        safe_results = _filter_safe_results(results)

        reranked_results = rerank_results(query, safe_results, ranking_profile=effective_profile)
        logger.info(f"Brave search found {len(reranked_results)} results")
        return reranked_results

    except Exception as e:
        logger.error(f"Brave search failed: {e}")
        raise


def serper_search(
    query: str,
    max_results: int = 3,
    api_key: str | None = None,
    ranking_profile: str = "balanced",
) -> list[dict[str, str]]:
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
    effective_profile = resolve_ranking_profile(query, ranking_profile)
    logger.info("Serper ranking profile resolved | profile=%s", effective_profile)

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
            results.append(_safe_search_result(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            ))

        safe_results = _filter_safe_results(results)

        reranked_results = rerank_results(query, safe_results, ranking_profile=effective_profile)
        logger.info(f"Serper search found {len(reranked_results)} results")
        return reranked_results

    except Exception as e:
        logger.error(f"Serper search failed: {e}")
        raise


def _supplement_missing_domains(
    results: list[dict[str, str]],
    domain_candidates: list[str],
    query: str,
    max_results: int,
    region: str,
    safesearch: str,
    ranking_profile: str,
) -> list[dict[str, str]]:
    """Run site:-scoped searches for expected domains missing from results.

    If supplemental results are found, they are merged in and the combined
    list is reranked; otherwise the original results are returned unchanged.
    """
    missing_domains = [
        domain for domain in domain_candidates
        if not any(_host_matches_domain(result.get("url", ""), domain) for result in results)
    ]
    if not missing_domains:
        return results

    supplemental_results: list[dict[str, str]] = []
    for domain in missing_domains:
        site_query = f"site:{domain} {query}"
        logger.info("Domain-focused supplemental search: %s", domain)
        supplemental_results.extend(
            web_search(
                site_query,
                max_results=max(1, min(5, max_results)),
                region=region,
                safesearch=safesearch,
                ranking_profile=ranking_profile,
            )
        )
    if not supplemental_results:
        return results

    merged_results = _merge_unique_results(results, supplemental_results)
    return rerank_results(query, merged_results, ranking_profile=ranking_profile)


def search_with_fallback(
    query: str,
    max_results: int = 3,
    region: str = "de-de",
    safesearch: str = "moderate",
    ranking_profile: str = "balanced",
) -> list[dict[str, str]]:
    """
    Search with automatic fallback to alternative providers.

    Tries in order: DuckDuckGo -> Brave -> Serper

    Args:
        query: Search query
        max_results: Maximum number of results
        region: Region code for search (default: de-de, should be passed from config)

    Returns:
        List of search results
    """
    cleaned_query, effective_region = resolve_search_preferences(query, default_region=region)
    effective_profile = resolve_ranking_profile(cleaned_query, ranking_profile)
    if not cleaned_query:
        logger.warning("Search with fallback skipped because cleaned query is empty")
        return []
    logger.info(
        "Fallback search preferences resolved | profile=%s | region=%s",
        effective_profile,
        effective_region,
    )

    domain_candidates = _extract_domain_candidates(cleaned_query, effective_region)

    # Try DuckDuckGo first
    try:
        results = web_search(
            cleaned_query,
            max_results=max_results,
            region=effective_region,
            safesearch=safesearch,
            ranking_profile=effective_profile,
        )
        if results:
            results = _supplement_missing_domains(
                results, domain_candidates, cleaned_query,
                max_results, effective_region, safesearch, effective_profile,
            )
            results = _promote_domain_matches(results, domain_candidates)
            return results[:max_results]
    except Exception as e:
        logger.warning(f"DuckDuckGo failed, trying fallback: {e}")

    # Try Brave
    try:
        return brave_search(cleaned_query, max_results, ranking_profile=effective_profile)
    except Exception as e:
        logger.warning(f"Brave search failed, trying Serper: {e}")

    # Try Serper
    try:
        return serper_search(cleaned_query, max_results, ranking_profile=effective_profile)
    except Exception as e:
        logger.error(f"All search providers failed: {e}")

    return []
