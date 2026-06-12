"""Wikipedia lookup tool."""
import logging
from typing import Optional, List
import wikipedia

logger = logging.getLogger("crawllama")


def wiki_lookup(
    query: str,
    lang: str = "de",
    sentences: int = 5
) -> Optional[str]:
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
        wikipedia.set_lang(lang)

        # Search and get page
        page = wikipedia.page(query, auto_suggest=True)

        # Get summary
        summary = wikipedia.summary(query, sentences=sentences)

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


def wiki_search(query: str, lang: str = "de", results: int = 5) -> List[str]:
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
        wikipedia.set_lang(lang)
        search_results = wikipedia.search(query, results=results)

        logger.info(f"Found {len(search_results)} Wikipedia pages")
        return search_results

    except Exception as e:
        logger.error(f"Wikipedia search failed: {e}")
        return []


def wiki_get_full_page(title: str, lang: str = "de") -> Optional[dict]:
    """
    Get full Wikipedia page content.

    Args:
        title: Page title
        lang: Language code

    Returns:
        Dictionary with page data or None
    """
    try:
        wikipedia.set_lang(lang)
        page = wikipedia.page(title)

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
