"""Fact checking against Wikipedia / web search for hallucination detection."""
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from difflib import SequenceMatcher
from typing import Any

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False

try:
    import wikipedia
    WIKIPEDIA_AVAILABLE = True
except ImportError:
    wikipedia = None
    WIKIPEDIA_AVAILABLE = False

from core.hallu.cache import LRUCache
from core.hallu.constants import FACT_CHECK_STOP_WORDS, WIKIPEDIA_SIMILARITY_THRESHOLD

logger = logging.getLogger("crawllama")


class FactChecker:
    """External fact-checking against knowledge sources."""
    
    def __init__(self, config: dict[str, Any]):
        """Initialize fact checker."""
        self.config = config
        self.wikipedia_enabled = config.get("wikipedia_check", True)
        self.web_search_enabled = config.get("web_search_check", False)
        self.wikipedia_timeout = config.get("wikipedia_timeout", 5.0)  # 5 seconds default timeout
        self.max_cache_size = config.get("max_cache_size", 100)  # Default: 100 entries
        self.cache = LRUCache(max_size=self.max_cache_size)
        
    def _call_with_timeout(self, func, timeout: float, *args, **kwargs):
        """
        Execute function with timeout protection.
        
        Args:
            func: Function to execute
            timeout: Timeout in seconds
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or None if timeout
        """
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            try:
                result = future.result(timeout=timeout)
                elapsed = time.time() - start_time
                logger.debug(f"Wikipedia {func.__name__} completed in {elapsed:.2f}s")
                return result
            except FuturesTimeoutError:
                logger.warning(f"Wikipedia {func.__name__} timed out after {timeout}s - implementing graceful fallback")
                return None
            except Exception as e:
                elapsed = time.time() - start_time  
                logger.debug(f"Wikipedia {func.__name__} failed after {elapsed:.2f}s: {e}")
                return None
        
    def check_facts(self, claims: list[str]) -> list[dict[str, Any]]:
        """
        Verify factual claims against external sources.
        
        Args:
            claims: List of factual claims to verify
            
        Returns:
            List of fact-check results
        """
        results = []
        
        for claim in claims:
            if len(claim.strip()) < 10:  # Skip very short claims
                continue
                
            result = {
                "claim": claim,
                "verified": False,
                "confidence": 0.0,
                "sources": [],
                "contradictions": []
            }
            
            # Wikipedia fact check
            if self.wikipedia_enabled:
                wiki_result = self._check_wikipedia(claim)
                result["sources"].extend(wiki_result["sources"])
                if wiki_result["verified"]:
                    result["verified"] = True
                    result["confidence"] = max(result["confidence"], wiki_result["confidence"])
                
            # Web search fact check (if enabled)
            if self.web_search_enabled:
                web_result = self._check_web_search(claim)
                result["sources"].extend(web_result["sources"])
                if web_result["verified"]:
                    result["verified"] = True
                    result["confidence"] = max(result["confidence"], web_result["confidence"])
                    
            results.append(result)
            
        return results
    
    def _check_wikipedia(self, claim: str) -> dict[str, Any]:
        """Check claim against Wikipedia with timeout protection."""
        if not WIKIPEDIA_AVAILABLE:
            logger.debug("Wikipedia module not available")
            return self._unverified_result()

        try:
            key_terms = self._extract_key_terms(claim)

            for term in key_terms[:2]:  # Limited to 2 terms for speed
                cached = self.cache.get(term)
                if cached:
                    # Cached terms are never re-fetched, even on a similarity miss
                    result = self._match_cached_entry(claim, cached)
                    if result:
                        return result
                    continue

                result = self._lookup_term_on_wikipedia(claim, term)
                if result:
                    return result

        except Exception as e:
            logger.warning(f"Wikipedia fact check failed: {e}")

        return self._unverified_result()

    def _match_cached_entry(self, claim: str, cached: dict[str, Any]) -> dict[str, Any] | None:
        """Verify claim against a cached Wikipedia entry, if similar enough."""
        similarity = self._calculate_similarity(claim.lower(), cached["content"].lower())
        if similarity <= WIKIPEDIA_SIMILARITY_THRESHOLD:
            return None
        return self._verified_result(cached["title"], cached["url"], similarity)

    def _lookup_term_on_wikipedia(self, claim: str, term: str) -> dict[str, Any] | None:
        """Search Wikipedia for a term and verify the claim against the top hit."""
        try:
            wikipedia.set_rate_limiting(True, min_wait=0.1)

            search_results = self._call_with_timeout(
                wikipedia.search,
                self.wikipedia_timeout,
                term,
                results=1
            )

            if search_results is None:
                logger.debug(f"Wikipedia search timed out for term '{term}'")
                return None
            if not search_results:
                return None

            return self._verify_claim_against_page(claim, term, search_results[0])

        except Exception as e:
            logger.debug(f"Wikipedia search failed for '{term}': {e}")
            return None

    def _verify_claim_against_page(self, claim: str, term: str, page_title: str) -> dict[str, Any] | None:
        """Fetch a Wikipedia page and check whether it supports the claim."""
        try:
            page = self._call_with_timeout(
                wikipedia.page,
                self.wikipedia_timeout,
                page_title
            )

            if page is None:
                logger.debug(f"Wikipedia page fetch timed out for '{page_title}'")
                return None

            content = page.content[:300]  # Small content slice for speed
            similarity = self._calculate_similarity(claim.lower(), content.lower())

            if similarity <= WIKIPEDIA_SIMILARITY_THRESHOLD:
                return None

            self.cache.set(term, {
                "content": content,
                "url": page.url,
                "title": page.title
            })
            return self._verified_result(page.title, page.url, similarity)

        except (wikipedia.exceptions.DisambiguationError,
                wikipedia.exceptions.PageError,
                wikipedia.exceptions.WikipediaException):
            # Skip problematic pages
            return None

    @staticmethod
    def _verified_result(title: str, url: str, similarity: float) -> dict[str, Any]:
        """Build a verified fact-check result with a single Wikipedia source."""
        return {
            "verified": True,
            "confidence": similarity,
            "sources": [{
                "type": "wikipedia",
                "title": title,
                "url": url,
                "similarity": similarity
            }]
        }

    @staticmethod
    def _unverified_result() -> dict[str, Any]:
        """Build an empty, unverified fact-check result."""
        return {"verified": False, "confidence": 0.0, "sources": []}
    
    def _check_web_search(self, claim: str) -> dict[str, Any]:
        """Check claim via web search (placeholder for integration)."""
        # Placeholder for web search integration
        # Could integrate with DuckDuckGo, Google Custom Search, etc.
        return self._unverified_result()

    def _extract_key_terms(self, text: str) -> list[str]:
        """Extract key terms from text for fact checking."""
        # Extract words (alphanumeric, 3+ chars)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

        # Filter out stop words and get unique terms
        key_terms = list(set(word for word in words if word not in FACT_CHECK_STOP_WORDS))

        # Sort by length (longer terms often more specific)
        return sorted(key_terms, key=len, reverse=True)
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity score."""
        return SequenceMatcher(None, text1, text2).ratio()
