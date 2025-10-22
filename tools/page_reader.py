"""Web page content extraction and parsing."""
import logging
from typing import Optional, List
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from utils.retry import fetch_with_retry
from utils.text_cleaner import clean_html, extract_contact_info
from utils.validators import is_safe_url

logger = logging.getLogger("crawllama")


def extract_links(html: str, base_url: str) -> List[str]:
    """
    Extract all links from HTML content, including important anchor links.

    Args:
        html: HTML content
        base_url: Base URL for resolving relative links

    Returns:
        List of absolute URLs
    """
    soup = BeautifulSoup(html, "html5lib")
    links = []
    base_domain = urlparse(base_url).netloc

    # Important anchor keywords to keep
    important_anchors = ['kontakt', 'contact', 'about', 'uber', 'impressum', 'datenschutz', 'privacy']

    for link in soup.find_all("a", href=True):
        href = link.get("href")
        # Convert relative URLs to absolute
        absolute_url = urljoin(base_url, href)

        # Only include links from the same domain
        if urlparse(absolute_url).netloc == base_domain:
            # Keep important anchor links, remove others
            if "#" in absolute_url:
                anchor = absolute_url.split("#")[1].lower() if len(absolute_url.split("#")) > 1 else ""
                if not any(keyword in anchor for keyword in important_anchors):
                    absolute_url = absolute_url.split("#")[0]

            if absolute_url and absolute_url not in links:
                links.append(absolute_url)

    return links


def read_page(url: str, max_length: int = 8000, include_links: bool = True) -> Optional[str]:
    """
    Fetch and extract text content from a web page with contact info and links.

    Args:
        url: URL to fetch
        max_length: Maximum text length (default 8000)
        include_links: Whether to include found links in the output

    Returns:
        Extracted text content with contact info and links or None if failed
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

        # Extract contact information
        contact_info = extract_contact_info(response.text)
        has_contact = contact_info["emails"] or contact_info["phones"]

        if has_contact:
            text += "\n\n--- Kontaktinformationen ---\n"
            if contact_info["emails"]:
                text += "E-Mail: " + ", ".join(contact_info["emails"]) + "\n"
            if contact_info["phones"]:
                text += "Telefon: " + ", ".join(contact_info["phones"][:3]) + "\n"  # Limit to 3 phones

        # Extract links if requested
        if include_links:
            links = extract_links(response.text, url)
            if links:
                text += f"\n--- Gefundene Unterseiten ({len(links)}) ---\n"
                text += "\n".join(f"- {link}" for link in links[:20])  # Limit to 20 links
                if len(links) > 20:
                    text += f"\n... und {len(links) - 20} weitere"

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
