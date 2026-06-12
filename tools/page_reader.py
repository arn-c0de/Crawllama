"""Web page content extraction and parsing."""
import html
import logging
import re
import unicodedata
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from utils.domain_blacklist import is_url_not_blacklisted
from utils.injection_detection import contains_obfuscated_injection
from utils.safe_fetch import safe_get
from utils.text_cleaner import clean_html, extract_contact_info

logger = logging.getLogger("crawllama")

def sanitize_for_output(text: str) -> str:
    """
    Escape HTML entities to prevent XSS attacks.
    
    This function protects against Cross-Site Scripting (XSS) by:
    1. Escaping HTML entities (<, >, &, ", ')
    2. Removing dangerous URL protocols (javascript:, data:, vbscript:)
    3. Preserving readability for normal text
    
    Args:
        text: Raw text that may contain HTML or malicious content
        
    Returns:
        Sanitized text safe for display in web contexts
    """
    if not text:
        return ""
    
    # 1. HTML entity escaping
    # This converts: <script> -> &lt;script&gt;
    text = html.escape(text)
    
    # 2. Remove dangerous URL protocols
    dangerous_protocols = [
        'javascript:', 'data:', 'vbscript:', 'file:',
        'about:', 'jar:', 'res:', 'ms-its:', 'mhtml:'
    ]
    
    for proto in dangerous_protocols:
        # Case-insensitive replacement
        text = re.sub(
            re.escape(proto),
            'blocked:',
            text,
            flags=re.IGNORECASE
        )
    
    return text


# Dangerous prompt-injection patterns filtered out of any externally-sourced
# text before it reaches the LLM (full page bodies AND search snippets/titles).
_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(?:all|previous|prior|any)\s+(?:previous\s+)?(?:instructions?|prompts?|commands?)",
    r"(?i)you\s+are\s+now\s+(?:a|an)\s+[\w\s]+(?:agent|assistant|bot|system|model)",
    r"(?i)(?:^|\n)\s*system\s*:",
    r"(?i)(?:^|\n)\s*assistant\s*:",
    r"(?i)(?:^|\n)\s*user\s*:",
    r"(?i)developer\s+mode",
    r"(?i)sudo\s+mode",
    r"(?i)jailbreak",
    r"(?i)reveal\s+(?:all|your|the)\s+(?:instructions?|prompts?|system\s+messages?)",
    r"(?i)what\s+(?:are|were)\s+your\s+(?:original|initial)\s+instructions?",
    r"(?i)repeat\s+(?:the|your)\s+(?:above|previous)\s+(?:instructions?|prompts?)",
    r"(?i)disregard\s+(?:all|previous|above)",
    r"(?i)new\s+instructions?:",
    r"(?i)override\s+(?:all|previous|any)?\s*(?:instructions?|prompts?|commands?)",
    # Neutralize attempts to forge the trust-boundary markers: untrusted content
    # containing the literal [EXTERNAL_WEB_CONTENT_START/END] token could close
    # the external-content block early and smuggle text in at system trust level.
    r"(?i)\[?\s*external_web_content_(?:start|end)\s*\]?",
]


def filter_prompt_injection(content: str) -> str:
    """Decode obfuscation and strip prompt-injection patterns from text.

    Shared by full-page sanitization and short search fragments so both
    untrusted-content paths get the same injection filtering. Does NOT add the
    external-content markers (callers that embed standalone blocks add those).
    """
    if not content:
        return ""

    # URL-decode up to 3 times to defeat single/double/triple encoding bypasses.
    import urllib.parse
    for _ in range(3):
        try:
            decoded = urllib.parse.unquote_plus(content)
            if decoded == content:
                break
            content = decoded
        except (TypeError, ValueError, UnicodeDecodeError):
            break

    # Unicode normalization to neutralize homograph/leetspeak obfuscation.
    try:
        content = unicodedata.normalize('NFKC', content)
    except (TypeError, ValueError):
        logger.debug("Unicode normalization failed during content sanitization")

    for pattern in _INJECTION_PATTERNS:
        content = re.sub(pattern, "[FILTERED_CONTENT]", content)

    if contains_obfuscated_injection(content):
        content = "[FILTERED_CONTENT]"

    return content


def sanitize_crawled_content_for_llm(content: str, max_length: int = 8000) -> str:
    """
    Sanitize crawled content to prevent prompt injection attacks.

    This function protects the LLM from manipulation attempts by:
    1. Decoding URL-encoded and Unicode obfuscation attempts
    2. Removing dangerous prompt injection patterns
    3. Limiting content length
    4. Marking content as external

    Args:
        content: Raw crawled content
        max_length: Maximum allowed content length

    Returns:
        Sanitized content safe for LLM processing
    """
    if not content:
        return ""

    # 1-2. Decode obfuscation and strip injection patterns (shared logic).
    content = filter_prompt_injection(content)

    # 3. Limit length to prevent token exhaustion
    if len(content) > max_length:
        content = content[:max_length] + "\n...[CONTENT_TRUNCATED_FOR_SAFETY]"

    # 4. Mark as external content for context separation
    return f"[EXTERNAL_WEB_CONTENT_START]\n{content}\n[EXTERNAL_WEB_CONTENT_END]"


def extract_links(html: str, base_url: str) -> list[str]:
    """
    Extract all links from HTML content, including important anchor links.

    Args:
        html: HTML content
        base_url: Base URL for resolving relative links

    Returns:
        List of absolute URLs
    """
    # SECURITY: html5lib parser prevents XXE attacks
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


def find_contact_pages(links: list[str]) -> list[str]:
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
    logger.info("Searching contact info")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted

    all_contacts = {
        "emails": set(),
        "phones": set(),
        "pages_checked": []
    }

    # Check main page first
    try:
        response = safe_get(url, timeout=10, max_size_mb=10)
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
                    logger.info("Checking contact page")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
                    subpage_response = safe_get(contact_url, timeout=10, max_size_mb=10)
                    if subpage_response:
                        content_type = subpage_response.headers.get("Content-Type", "")
                        if "text/html" not in content_type:
                            continue
                        subpage_contact = extract_contact_info(subpage_response.text)
                        all_contacts["emails"].update(subpage_contact["emails"])
                        all_contacts["phones"].update(subpage_contact["phones"])
                        all_contacts["pages_checked"].append(contact_url)
                except Exception as e:
                    logger.warning(f"Failed to check contact page: {e}")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted

    except Exception as e:
        logger.error(f"Failed to search contact info: {e}")

    # Convert sets to lists
    all_contacts["emails"] = list(all_contacts["emails"])
    all_contacts["phones"] = list(all_contacts["phones"])

    logger.info(f"Total found: {len(all_contacts['emails'])} emails, {len(all_contacts['phones'])} phones")

    return all_contacts


def _fetch_html_page(url: str) -> requests.Response | None:
    """Fetch a URL via safe_get and return the response only if it is HTML."""
    # Fetch with safe_get (includes retry, rate limiting, robots.txt, size limit)
    response = safe_get(url, timeout=10, max_size_mb=20)

    if response is None:
        logger.warning("Failed to fetch page")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
        return None

    # Check content type
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        # lgtm[py/clear-text-logging-sensitive-data] - Not logging content type to avoid false positive
        logger.warning("Non-HTML content type detected")
        return None

    return response


def _build_contact_block(
    emails: list[str],
    phones: list[str],
    phone_limit: int,
    pages_checked: list[str] | None = None,
) -> str | None:
    """Build a formatted contact information block, or None if nothing was found."""
    if not emails and not phones:
        return None

    contact_block = "\n--- Contact Information ---\n"
    if emails:
        # Sanitize emails to prevent XSS
        safe_emails = [sanitize_for_output(email) for email in emails]
        contact_block += "Email: " + ", ".join(safe_emails) + "\n"
    if phones:
        # Sanitize phone numbers to prevent XSS
        safe_phones = [sanitize_for_output(phone) for phone in phones[:phone_limit]]
        contact_block += "Phone: " + ", ".join(safe_phones) + "\n"
    if pages_checked is not None and len(pages_checked) > 1:
        contact_block += f"\n(Found on {len(pages_checked)} pages)"

    return contact_block


def _extract_contact_block(url: str, page_html: str, smart_contact_search: bool) -> str | None:
    """Extract contact information from the page (and subpages if smart search)."""
    if smart_contact_search:
        # Use intelligent contact search
        all_contacts = search_contact_info(url, max_subpages=3)
        return _build_contact_block(
            all_contacts["emails"],
            all_contacts["phones"],
            phone_limit=5,
            pages_checked=all_contacts["pages_checked"],
        )

    # Simple contact extraction
    contact_info = extract_contact_info(page_html)
    return _build_contact_block(
        contact_info["emails"],
        contact_info["phones"],
        phone_limit=3,
    )


def _build_link_blocks(page_html: str, url: str) -> list[str]:
    """Build formatted blocks listing contact subpages and additional subpages."""
    links = extract_links(page_html, url)
    if not links:
        return []

    blocks = []

    # Highlight contact pages
    contact_pages = find_contact_pages(links)
    if contact_pages:
        links_block = f"\n--- Contact Subpages ({len(contact_pages)}) ---\n"
        # Sanitize URLs to prevent XSS in links
        safe_contact_pages = [sanitize_for_output(link) for link in contact_pages[:10]]
        links_block += "\n".join(f"- {link}" for link in safe_contact_pages)
        blocks.append(links_block)

    # Show other pages
    other_pages = [link for link in links if link not in contact_pages]
    if other_pages:
        other_block = f"\n--- Additional Subpages ({len(other_pages)}) ---\n"
        # Sanitize URLs to prevent XSS in links
        safe_other_pages = [sanitize_for_output(link) for link in other_pages[:15]]
        other_block += "\n".join(f"- {link}" for link in safe_other_pages)
        if len(other_pages) > 15:
            other_block += f"\n... and {len(other_pages) - 15} more"
        blocks.append(other_block)

    return blocks


def read_page(
    url: str,
    max_length: int = 8000,
    include_links: bool = True,
    smart_contact_search: bool = True,
    include_contact_info: bool = True,
) -> str | None:
    """
    Fetch and extract text content from a web page with contact info and links.

    Args:
        url: URL to fetch
        max_length: Maximum text length (default 8000)
        include_links: Whether to include found links in the output
        smart_contact_search: Whether to search contact pages automatically
        include_contact_info: Whether to append extracted contact blocks

    Returns:
        Extracted text content with contact info and links or None if failed
    """
    logger.info("Reading page")  # lgtm[py/clear-text-logging-sensitive-data] - URL content not logged to avoid leaking data

    # Validate URL (blacklist check)
    if not is_url_not_blacklisted(url):
        logger.warning("URL blocked by blacklist")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
        return None

    try:
        response = _fetch_html_page(url)
        if response is None:
            return None

        # Extract text
        text = clean_html(response.text, max_length=max_length)

        # Sanitize content to prevent prompt injection attacks
        text = sanitize_crawled_content_for_llm(text, max_length=max_length)

        # Extract contact information
        if include_contact_info:
            contact_block = _extract_contact_block(url, response.text, smart_contact_search)
            if contact_block:
                text += "\n" + sanitize_crawled_content_for_llm(contact_block, max_length=max_length)

        # Extract links if requested
        if include_links:
            for link_block in _build_link_blocks(response.text, url):
                text += "\n" + sanitize_crawled_content_for_llm(link_block, max_length=max_length)

        logger.info(f"Extracted {len(text)} characters from page")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
        return text

    except requests.RequestException as e:
        logger.error(f"Failed to read page: {e}")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
        return None
    except Exception as e:
        logger.error(f"Unexpected error reading page: {e}")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
        return None


def extract_main_content(html: str) -> str | None:
    """
    Extract main content from HTML, trying to identify the main article.

    SECURITY: Uses html5lib parser which is safe against XXE attacks.
    - html5lib is a pure-Python parser that doesn't use XML parsers
    - Immune to XXE (XML External Entity) attacks
    - Safe for untrusted HTML content

    Args:
        html: Raw HTML content

    Returns:
        Main content text or None
    """
    # SECURITY: html5lib parser prevents XXE attacks
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
        response = safe_get(url, timeout=10, max_size_mb=5)
        if response is None:
            return {"url": url, "title": "", "description": "", "keywords": []}

        # SECURITY: html5lib parser prevents XXE attacks
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

    except Exception:
        logger.error("Failed to extract metadata from page: error occurred")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
        return {"url": "REDACTED", "title": "", "description": "", "keywords": []}
