"""Web search tool using DuckDuckGo with fallback support."""
import logging
import os
import time
import re
import html
from urllib.parse import urlparse
from typing import List, Dict, Optional, Tuple
from ddgs import DDGS
from utils.domain_blacklist import filter_safe_urls
from utils.validators import sanitize_for_logging
from tools.page_reader import filter_prompt_injection

logger = logging.getLogger("crawllama")

COUNTRY_TO_REGION = {
    "de": "de-de", "deutschland": "de-de", "germany": "de-de",
    "us": "us-en", "usa": "us-en", "united-states": "us-en", "united_states": "us-en",
    "uk": "uk-en", "gb": "uk-en", "united-kingdom": "uk-en", "great-britain": "uk-en",
    "fr": "fr-fr", "france": "fr-fr",
    "es": "es-es", "spain": "es-es",
    "it": "it-it", "italy": "it-it",
    "nl": "nl-nl", "netherlands": "nl-nl",
    "pl": "pl-pl", "poland": "pl-pl",
    "pt": "pt-pt", "portugal": "pt-pt",
    "at": "at-de", "austria": "at-de",
    "ch": "ch-de", "switzerland": "ch-de",
    "be": "be-fr", "belgium": "be-fr",
    "ca": "ca-en", "canada": "ca-en",
    "au": "au-en", "australia": "au-en",
    "br": "br-pt", "brazil": "br-pt",
    "mx": "mx-es", "mexico": "mx-es",
    "jp": "jp-jp", "japan": "jp-jp",
    "kr": "kr-kr", "korea": "kr-kr",
    "cn": "cn-zh", "china": "cn-zh",
    "in": "in-en", "india": "in-en",
    "ru": "ru-ru", "russia": "ru-ru",
}

LANG_TO_REGION = {
    "de": "de-de",
    "en": "us-en",
    "fr": "fr-fr",
    "es": "es-es",
    "it": "it-it",
    "nl": "nl-nl",
    "pl": "pl-pl",
    "pt": "pt-pt",
    "ja": "jp-jp",
    "ko": "kr-kr",
    "zh": "cn-zh",
    "ru": "ru-ru",
}

RANKING_PROFILES = {
    "balanced": {
        "base_order": 1.0,
        "exact_title": 5.0,
        "exact_snippet": 2.5,
        "title_overlap": 1.0,
        "snippet_overlap": 0.4,
        "coverage": 1.5,
        "trust": 1.0,
    },
    "strict_factual": {
        "base_order": 0.8,
        "exact_title": 5.5,
        "exact_snippet": 2.0,
        "title_overlap": 1.2,
        "snippet_overlap": 0.25,
        "coverage": 1.8,
        "trust": 1.4,
    },
    "osint": {
        "base_order": 1.0,
        "exact_title": 6.0,
        "exact_snippet": 3.0,
        "title_overlap": 1.15,
        "snippet_overlap": 0.55,
        "coverage": 2.0,
        "trust": 0.75,
    },
}

OSINT_PROFILE_HINTS = (
    "email:",
    "phone:",
    "phonenumber:",
    "domain:",
    "ip:",
    "username:",
    "site:",
    "inurl:",
    "intext:",
    "intitle:",
    "filetype:",
)

STRICT_FACTUAL_HINTS = (
    "official",
    "government",
    "regulation",
    "law",
    "statistic",
    "statistics",
    "report",
    "whitepaper",
    "documentation",
    "specification",
    "source",
    "citation",
    "studie",
    "gesetz",
    "verordnung",
    "offiziell",
    "quelle",
)


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


def _extract_inline_operator(query: str, operator: str) -> Tuple[Optional[str], str]:
    """Extract operator value from query and return cleaned query."""
    pattern = rf"(?i)(?:^|\s){re.escape(operator)}:(?:\"([^\"]+)\"|([^\s]+))"
    match = re.search(pattern, query)
    if not match:
        return None, query

    value = (match.group(1) or match.group(2) or "").strip()
    cleaned = (query[:match.start()] + " " + query[match.end():]).strip()
    cleaned = " ".join(cleaned.split())
    return value or None, cleaned


def _tokenize_query_text(text: str) -> List[str]:
    """Tokenize text for simple lexical relevance scoring."""
    return re.findall(r"[a-z0-9]{2,}", text.lower())


def _domain_trust_score(url: str) -> float:
    """Assign a lightweight trust prior based on TLD/domain patterns."""
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except Exception:
        return 0.0

    if not host:
        return 0.0

    score = 0.0
    if host.endswith(".gov") or host.endswith(".gov.uk"):
        score += 1.2
    if host.endswith(".edu"):
        score += 1.0
    if host.endswith(".org"):
        score += 0.5
    if host.startswith("www."):
        score += 0.05
    if host == "wikipedia.org" or host.endswith(".wikipedia.org"):
        score += 0.8
    return score


def rerank_results(
    query: str,
    results: List[Dict[str, str]],
    ranking_profile: str = "balanced",
) -> List[Dict[str, str]]:
    """Re-rank search results by lexical relevance and lightweight domain trust."""
    if not results:
        return results

    profile = RANKING_PROFILES.get((ranking_profile or "balanced").lower(), RANKING_PROFILES["balanced"])
    normalized_query = (query or "").strip().lower()
    query_tokens = _tokenize_query_text(normalized_query)
    query_token_set = set(query_tokens)

    ranked: List[Tuple[float, Dict[str, str]]] = []
    for idx, result in enumerate(results):
        title = (result.get("title") or "").lower()
        snippet = (result.get("snippet") or "").lower()
        url = result.get("url") or ""
        combined_text = f"{title} {snippet}"

        score = 0.0

        # Preserve original provider order as mild tie-breaker
        score += max(0.0, profile["base_order"] - idx * 0.03)

        # Exact phrase matches are strong signals
        if normalized_query and normalized_query in title:
            score += profile["exact_title"]
        if normalized_query and normalized_query in snippet:
            score += profile["exact_snippet"]

        # Token overlap (title weighted stronger than snippet)
        if query_token_set:
            title_tokens = set(_tokenize_query_text(title))
            snippet_tokens = set(_tokenize_query_text(snippet))
            score += len(query_token_set & title_tokens) * profile["title_overlap"]
            score += len(query_token_set & snippet_tokens) * profile["snippet_overlap"]

            # Coverage bonus if most query tokens appear anywhere
            combined_tokens = set(_tokenize_query_text(combined_text))
            coverage = len(query_token_set & combined_tokens) / max(1, len(query_token_set))
            score += coverage * profile["coverage"]

        score += _domain_trust_score(url) * profile["trust"]

        ranked.append((score, result))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked]


def resolve_region_from_preferences(
    default_region: str = "de-de",
    region: Optional[str] = None,
    country: Optional[str] = None,
    lang: Optional[str] = None,
) -> str:
    """Resolve DDGS region code from explicit region/country/lang preferences."""
    if region:
        normalized_region = region.strip().lower()
        if re.match(r"^[a-z]{2}-[a-z]{2}$", normalized_region):
            return normalized_region
        mapped_from_country = COUNTRY_TO_REGION.get(normalized_region)
        if mapped_from_country:
            return mapped_from_country

    if country:
        normalized_country = country.strip().lower().replace(" ", "-")
        mapped_from_country = COUNTRY_TO_REGION.get(normalized_country)
        if mapped_from_country:
            return mapped_from_country

    if lang:
        normalized_lang = lang.strip().lower()
        mapped_from_lang = LANG_TO_REGION.get(normalized_lang)
        if mapped_from_lang:
            return mapped_from_lang

    return default_region


def resolve_search_preferences(query: str, default_region: str = "de-de") -> Tuple[str, str]:
    """
    Resolve query-level search preferences.

    Supports inline operators in plain search queries:
    - country:us / country:germany
    - lang:en
    - region:us-en
    """
    cleaned_query = query.strip()

    region_hint, cleaned_query = _extract_inline_operator(cleaned_query, "region")
    country_hint, cleaned_query = _extract_inline_operator(cleaned_query, "country")
    lang_hint, cleaned_query = _extract_inline_operator(cleaned_query, "lang")

    effective_region = resolve_region_from_preferences(
        default_region=default_region,
        region=region_hint,
        country=country_hint,
        lang=lang_hint,
    )

    return cleaned_query, effective_region


def resolve_ranking_profile(query: str, requested_profile: str = "balanced") -> str:
    """
    Resolve ranking profile from config/inline operators/query intent.

    Supported explicit inline operators:
    - ranking:<profile>
    - profile:<profile>

    Automatic mode:
    - requested_profile in {"auto", "adaptive"}
    """
    effective_profile = (requested_profile or "balanced").strip().lower()
    cleaned_query = (query or "").strip()

    ranking_hint, _ = _extract_inline_operator(cleaned_query, "ranking")
    profile_hint, _ = _extract_inline_operator(cleaned_query, "profile")
    explicit_profile = (ranking_hint or profile_hint or "").strip().lower()
    if explicit_profile in RANKING_PROFILES:
        return explicit_profile

    if effective_profile not in ("auto", "adaptive"):
        return effective_profile if effective_profile in RANKING_PROFILES else "balanced"

    lowered = cleaned_query.lower()
    if any(hint in lowered for hint in OSINT_PROFILE_HINTS):
        return "osint"

    if any(hint in lowered for hint in STRICT_FACTUAL_HINTS):
        return "strict_factual"

    return "balanced"


def _extract_domain_candidates(query: str, region: str) -> List[str]:
    """Extract likely domain candidates from a query for supplemental site-specific lookups."""
    lowered_query = (query or "").lower()
    if not lowered_query or "site:" in lowered_query:
        return []

    explicit_domains = re.findall(r"\b[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.[a-z]{2,}\b", lowered_query)
    if explicit_domains:
        deduped: List[str] = []
        for domain in explicit_domains:
            if domain not in deduped:
                deduped.append(domain)
        return deduped[:2]

    tld = ".de" if (region or "").lower().startswith("de-") else ".com"
    brand_tokens = re.findall(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", lowered_query)
    candidates: List[str] = []
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
    primary: List[Dict[str, str]],
    secondary: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """Merge search results without duplicate URLs."""
    merged: List[Dict[str, str]] = []
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
    results: List[Dict[str, str]],
    domains: List[str],
    max_promoted_per_domain: int = 1,
) -> List[Dict[str, str]]:
    """Move domain-matching results to the front so they appear in source references."""
    if not results or not domains:
        return results

    promoted: List[Dict[str, str]] = []
    remaining: List[Dict[str, str]] = []
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


def web_search(
    query: str,
    max_results: int = 3,
    region: str = "de-de",
    safesearch: str = "moderate",
    ranking_profile: str = "balanced",
) -> List[Dict[str, str]]:
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
        results = []
        
        # DDGS-specific error handling with retry logic
        max_retries = 2
        retry_delay = 1.0
        
        for attempt in range(max_retries + 1):
            try:
                with DDGS() as ddgs:
                    search_results = ddgs.text(
                        cleaned_query,
                        max_results=max_results,
                        region=effective_region,
                        safesearch=safesearch
                    )

                    for r in search_results:
                        # Debug: Log what fields are available
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Raw search result keys: {list(r.keys())}")

                        # ddgs uses 'href' for URL, 'body' for snippet
                        # Old duckduckgo_search used 'link' and 'body'
                        url = r.get("href") or r.get("link") or r.get("url") or ""
                        title = _sanitize_text_fragment(r.get("title") or "", max_chars=180)
                        snippet = _sanitize_text_fragment(
                            r.get("body") or r.get("snippet") or r.get("description") or "",
                            max_chars=320,
                        )

                        if url:  # Only add if we have a URL
                            results.append({
                                "title": title,
                                "url": url,
                                "snippet": snippet
                            })
                            logger.debug(f"✓ Added result: {title[:50]} - {url}")
                        else:
                            logger.warning(f"✗ Skipping result with no URL: {title[:50]}")
                
                # If we got here, search was successful - break retry loop
                break
                
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning(f"DDGS connection error on attempt {attempt + 1}/{max_retries + 1}: {e}")
                if attempt < max_retries:
                    logger.info(f"Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("All DDGS retry attempts failed")
                    return []
                    
            except Exception as e:
                logger.error(f"DDGS search failed with unexpected error: {e}")
                if attempt < max_retries:
                    logger.info(f"Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return []

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
        
        # DDGS news search with retry logic
        max_retries = 2
        retry_delay = 1.0
        
        for attempt in range(max_retries + 1):
            try:
                with DDGS() as ddgs:
                    news_results = ddgs.news(query, max_results=max_results)

                    for r in news_results:
                        results.append({
                            "title": _sanitize_text_fragment(r.get("title", ""), max_chars=180),
                            "url": r.get("url", ""),
                            "snippet": _sanitize_text_fragment(r.get("body", ""), max_chars=320),
                            "date": r.get("date", ""),
                            "source": r.get("source", "")
                        })
                
                # If we got here, search was successful - break retry loop
                break
                
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning(f"DDGS news search connection error on attempt {attempt + 1}/{max_retries + 1}: {e}")
                if attempt < max_retries:
                    logger.info(f"Retrying news search in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("All DDGS news search retry attempts failed")
                    return []
                    
            except Exception as e:
                logger.error(f"DDGS news search failed with unexpected error: {e}")
                if attempt < max_retries:
                    logger.info(f"Retrying news search in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return []

        logger.info(f"Found {len(results)} news articles")
        return results

    except Exception as e:
        logger.error(f"News search failed with critical error: {e}")
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
    api_key: Optional[str] = None,
    ranking_profile: str = "balanced",
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
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": _sanitize_text_fragment(item.get("description", ""), max_chars=320)
            })

        # Filter blacklisted URLs
        safe_urls = filter_safe_urls([r["url"] for r in results])
        safe_results = [r for r in results if r["url"] in safe_urls]

        reranked_results = rerank_results(query, safe_results, ranking_profile=effective_profile)
        logger.info(f"Brave search found {len(reranked_results)} results")
        return reranked_results

    except Exception as e:
        logger.error(f"Brave search failed: {e}")
        raise


def serper_search(
    query: str,
    max_results: int = 3,
    api_key: Optional[str] = None,
    ranking_profile: str = "balanced",
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
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": _sanitize_text_fragment(item.get("snippet", ""), max_chars=320)
            })

        # Filter blacklisted URLs
        safe_urls = filter_safe_urls([r["url"] for r in results])
        safe_results = [r for r in results if r["url"] in safe_urls]

        reranked_results = rerank_results(query, safe_results, ranking_profile=effective_profile)
        logger.info(f"Serper search found {len(reranked_results)} results")
        return reranked_results

    except Exception as e:
        logger.error(f"Serper search failed: {e}")
        raise


def search_with_fallback(
    query: str,
    max_results: int = 3,
    region: str = "de-de",
    safesearch: str = "moderate",
    ranking_profile: str = "balanced",
) -> List[Dict[str, str]]:
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
            missing_domains = [
                domain for domain in domain_candidates
                if not any(_host_matches_domain(result.get("url", ""), domain) for result in results)
            ]
            if missing_domains:
                supplemental_results: List[Dict[str, str]] = []
                for domain in missing_domains:
                    site_query = f"site:{domain} {cleaned_query}"
                    logger.info("Domain-focused supplemental search: %s", domain)
                    supplemental_results.extend(
                        web_search(
                            site_query,
                            max_results=max(1, min(5, max_results)),
                            region=effective_region,
                            safesearch=safesearch,
                            ranking_profile=effective_profile,
                        )
                    )
                if supplemental_results:
                    merged_results = _merge_unique_results(results, supplemental_results)
                    results = rerank_results(
                        cleaned_query,
                        merged_results,
                        ranking_profile=effective_profile,
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
