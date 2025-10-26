"""Web page content extraction and parsing."""
import logging
from typing import Optional, List
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from utils.safe_fetch import safe_get
from utils.text_cleaner import clean_html, extract_contact_info
from utils.domain_blacklist import is_url_not_blacklisted
from utils.validators import sanitize_url_for_logging

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


def find_contact_pages(links: List[str]) -> List[str]:
    """
    Filter links to find potential contact pages.

    Args:
        links: List of URLs

    Returns:
        List of potential contact page URLs
    """
    contact_keywords = [
        'kontakt', 'contact', 'impressum', 'imprint',
        'about', 'uber', 'über', 'datenschutz', 'privacy',
        'anfahrt', 'location', 'team', 'unternehmen', 'company'
    ]

    contact_pages = []
    for link in links:
        link_lower = link.lower()
        if any(keyword in link_lower for keyword in contact_keywords):
            contact_pages.append(link)

    return contact_pages


def search_contact_info(url: str, max_subpages: int = 3) -> dict:
    """
    Intelligently search for contact information on a website.

    Searches main page and relevant subpages (kontakt, impressum, etc.)

    Args:
        url: Main URL to search
        max_subpages: Maximum number of subpages to check (default 3)

    Returns:
        Dictionary with all found contact information
    """
    logger.info(f"Searching contact info for: {url}")

    all_contacts = {
        "emails": set(),
        "phones": set(),
        "pages_checked": []
    }

    # Check main page first
    try:
        response = safe_get(url, timeout=10)
        if response:
            contact_info = extract_contact_info(response.text)
            all_contacts["emails"].update(contact_info["emails"])
            all_contacts["phones"].update(contact_info["phones"])
            all_contacts["pages_checked"].append(url)

            # Extract and filter links
            links = extract_links(response.text, url)
            contact_pages = find_contact_pages(links)

            logger.info(f"Found {len(contact_pages)} potential contact pages")

            # Check contact pages
            for contact_url in contact_pages[:max_subpages]:
                try:
                    logger.info(f"Checking contact page: {contact_url}")
                    subpage_response = safe_get(contact_url, timeout=10)
                    if subpage_response:
                        subpage_contact = extract_contact_info(subpage_response.text)
                        all_contacts["emails"].update(subpage_contact["emails"])
                        all_contacts["phones"].update(subpage_contact["phones"])
                        all_contacts["pages_checked"].append(contact_url)
                except Exception as e:
                    logger.warning(f"Failed to check {contact_url}: {e}")

    except Exception as e:
        logger.error(f"Failed to search contact info: {e}")

    # Convert sets to lists
    all_contacts["emails"] = list(all_contacts["emails"])
    all_contacts["phones"] = list(all_contacts["phones"])

    logger.info(f"Total found: {len(all_contacts['emails'])} emails, {len(all_contacts['phones'])} phones")

    return all_contacts


def read_page(url: str, max_length: int = 8000, include_links: bool = True, smart_contact_search: bool = True) -> Optional[str]:
    """
    Fetch and extract text content from a web page with contact info and links.

    Args:
        url: URL to fetch
        max_length: Maximum text length (default 8000)
        include_links: Whether to include found links in the output
        smart_contact_search: Whether to search contact pages automatically

    Returns:
        Extracted text content with contact info and links or None if failed
    """
    logger.info(f"Reading page: {url}")

    # Validate URL (blacklist check)
    if not is_url_not_blacklisted(url):
        logger.warning(f"URL blocked by blacklist: {url}")
        return None

    try:
        # Fetch with safe_get (includes retry, rate limiting, robots.txt)
        response = safe_get(url, timeout=10)

        if response is None:
            logger.warning(f"Failed to fetch {url}")
            return None

        # Check content type
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            logger.warning(f"Non-HTML content type: {content_type}")
            return None

        # Extract text
        text = clean_html(response.text, max_length=max_length)

        # Extract contact information
        if smart_contact_search:
            # Use intelligent contact search
            all_contacts = search_contact_info(url, max_subpages=3)
            has_contact = all_contacts["emails"] or all_contacts["phones"]

            if has_contact:
                text += "\n\n--- Kontaktinformationen ---\n"
                if all_contacts["emails"]:
                    text += "E-Mail: " + ", ".join(all_contacts["emails"]) + "\n"
                if all_contacts["phones"]:
                    text += "Telefon: " + ", ".join(all_contacts["phones"][:5]) + "\n"
                if len(all_contacts["pages_checked"]) > 1:
                    text += f"\n(Gefunden auf {len(all_contacts['pages_checked'])} Seiten)"
        else:
            # Simple contact extraction
            contact_info = extract_contact_info(response.text)
            has_contact = contact_info["emails"] or contact_info["phones"]

            if has_contact:
                text += "\n\n--- Kontaktinformationen ---\n"
                if contact_info["emails"]:
                    text += "E-Mail: " + ", ".join(contact_info["emails"]) + "\n"
                if contact_info["phones"]:
                    text += "Telefon: " + ", ".join(contact_info["phones"][:3]) + "\n"

        # Extract links if requested
        if include_links:
            links = extract_links(response.text, url)
            if links:
                # Highlight contact pages
                contact_pages = find_contact_pages(links)
                if contact_pages:
                    text += f"\n--- Kontakt-Unterseiten ({len(contact_pages)}) ---\n"
                    text += "\n".join(f"- {link}" for link in contact_pages[:10])

                # Show other pages
                other_pages = [l for l in links if l not in contact_pages]
                if other_pages:
                    text += f"\n\n--- Weitere Unterseiten ({len(other_pages)}) ---\n"
                    text += "\n".join(f"- {link}" for link in other_pages[:15])
                    if len(other_pages) > 15:
                        text += f"\n... und {len(other_pages) - 15} weitere"

        logger.info(f"Extracted {len(text)} characters from {sanitize_url_for_logging(url)}")
        return text

    except requests.RequestException as e:
        logger.error(f"Failed to read page {sanitize_url_for_logging(url)}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error reading {sanitize_url_for_logging(url)}: {e}")
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
        response = safe_get(url, timeout=10)
        if response is None:
            return {"url": url, "title": "", "description": "", "keywords": []}

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
        logger.error(f"Failed to extract metadata from {sanitize_url_for_logging(url)}: {e}")
        return {"url": url, "title": "", "description": "", "keywords": []}
