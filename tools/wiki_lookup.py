"""Wikipedia lookup tool."""
import logging
import threading
from contextlib import contextmanager

import wikipedia

logger = logging.getLogger("crawllama")

# wikipedia.set_lang() changes a process-wide setting; hold this lock while a
# language is set so concurrent lookups in other languages can't interleave.
_wikipedia_lock = threading.Lock()


@contextmanager
def _wikipedia_language(lang: str):
    """Use ``lang`` for the wikipedia calls inside the block (thread-safe)."""
    with _wikipedia_lock:
        wikipedia.set_lang(lang)
        yield


def wiki_lookup(
    query: str,
    lang: str = "de",
    sentences: int = 5
) -> str | None:
    """
    Look up information on Wikipedia.

    Args:
        query: Search query
        lang: Language code (de, en, etc.)
        sentences: Number of sentences to return

    Returns:
        Summary text or None if not found
    """
    logger.info(f"Wikipedia lookup: '{query}' (lang={lang})")

    try:
        with _wikipedia_language(lang):
            # Search and get page
            page = wikipedia.page(query, auto_suggest=True)

            # Summary of exactly that page: summary(query) would resolve the
            # query again (with auto-suggest) and could return another article
            summary = wikipedia.summary(page.title, sentences=sentences, auto_suggest=False)

        logger.info(f"Found Wikipedia page: {page.title}")
        return summary

    except wikipedia.DisambiguationError as e:
        # Multiple possible pages
        logger.warning(f"Wikipedia disambiguation for '{query}'")
        options = ", ".join(e.options[:5])
        return f"Ambiguous term. Possible meanings: {options}"

    except wikipedia.PageError:
        logger.warning(f"Wikipedia page not found: '{query}'")
        return None

    except Exception as e:
        logger.error(f"Wikipedia lookup failed: {e}")
        return None


def wiki_search(query: str, lang: str = "de", results: int = 5) -> list[str]:
    """
    Search for Wikipedia pages.

    Args:
        query: Search query
        lang: Language code
        results: Number of results

    Returns:
        List of page titles
    """
    logger.info(f"Wikipedia search: '{query}'")

    try:
        with _wikipedia_language(lang):
            search_results = wikipedia.search(query, results=results)

        logger.info(f"Found {len(search_results)} Wikipedia pages")
        return search_results

    except Exception as e:
        logger.error(f"Wikipedia search failed: {e}")
        return []


def wiki_get_full_page(title: str, lang: str = "de") -> dict | None:
    """
    Get full Wikipedia page content.

    Args:
        title: Page title
        lang: Language code

    Returns:
        Dictionary with page data or None
    """
    try:
        with _wikipedia_language(lang):
            page = wikipedia.page(title)
            # Page properties are fetched lazily, so read them while the
            # language is still set
            return {
                "title": page.title,
                "url": page.url,
                "summary": page.summary,
                "content": page.content,
                "links": page.links[:20]  # First 20 links
            }

    except Exception as e:
        logger.error(f"Failed to get Wikipedia page '{title}': {e}")
        return None
