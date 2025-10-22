"""Web page content extraction and parsing."""
import logging
from typing import Optional
import requests
from bs4 import BeautifulSoup
from utils.retry import fetch_with_retry
from utils.text_cleaner import clean_html
from utils.validators import is_safe_url

logger = logging.getLogger("crawllama")


def read_page(url: str, max_length: int = 3000) -> Optional[str]:
    """
    Fetch and extract text content from a web page.

    Args:
        url: URL to fetch
        max_length: Maximum text length

    Returns:
        Extracted text content or None if failed
    """
    logger.info(f"Reading page: {url}")

    # Validate URL
    if not is_safe_url(url):
        logger.warning(f"Unsafe URL rejected: {url}")
        return None

    try:
        # Fetch with retry
        response = fetch_with_retry(url, timeout=10)

        # Check content type
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            logger.warning(f"Non-HTML content type: {content_type}")
            return None

        # Extract text
        text = clean_html(response.text, max_length=max_length)

        logger.info(f"Extracted {len(text)} characters from {url}")
        return text

    except requests.RequestException as e:
        logger.error(f"Failed to read page {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error reading {url}: {e}")
        return None


def extract_main_content(html: str) -> Optional[str]:
    """
    Extract main content from HTML, trying to identify the main article.

    Args:
        html: Raw HTML content

    Returns:
        Main content text or None
    """
    soup = BeautifulSoup(html, "html5lib")

    # Try to find main content containers
    main_selectors = [
        "article",
        "main",
        "[role='main']",
        ".main-content",
        "#main-content",
        ".article-content",
        ".post-content"
    ]

    for selector in main_selectors:
        main_content = soup.select_one(selector)
        if main_content:
            return clean_html(str(main_content))

    # Fallback to all content
    return clean_html(html)


def extract_metadata(url: str) -> dict:
    """
    Extract metadata from a web page.

    Args:
        url: URL to fetch

    Returns:
        Dictionary with metadata (title, description, etc.)
    """
    try:
        response = fetch_with_retry(url, timeout=10)
        soup = BeautifulSoup(response.text, "html5lib")

        metadata = {
            "url": url,
            "title": "",
            "description": "",
            "keywords": []
        }

        # Extract title
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)

        # Extract meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            metadata["description"] = meta_desc.get("content", "")

        # Extract keywords
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords:
            keywords = meta_keywords.get("content", "")
            metadata["keywords"] = [k.strip() for k in keywords.split(",")]

        return metadata

    except Exception as e:
        logger.error(f"Failed to extract metadata from {url}: {e}")
        return {"url": url, "title": "", "description": "", "keywords": []}
