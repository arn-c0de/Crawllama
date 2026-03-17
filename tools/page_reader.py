"""Web page content extraction and parsing."""
import base64
import binascii
import html
import logging
import re
from typing import Optional, List
from urllib.parse import urljoin, urlparse
import unicodedata
import requests
from bs4 import BeautifulSoup
from utils.safe_fetch import safe_get
from utils.text_cleaner import clean_html, extract_contact_info
from utils.domain_blacklist import is_url_not_blacklisted
from utils.validators import sanitize_url_for_logging

logger = logging.getLogger("crawllama")

_ZERO_WIDTH_RE = re.compile(r"[\u00ad\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_LEET_TRANSLATION = str.maketrans({
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "$": "s",
    "@": "a",
})
_HOMOGLYPH_TRANSLATION = str.maketrans({
    # Common Cyrillic homoglyphs used in prompt injection obfuscation
    "а": "a", "А": "A",
    "е": "e", "Е": "E",
    "о": "o", "О": "O",
    "р": "p", "Р": "P",
    "с": "c", "С": "C",
    "у": "y", "У": "Y",
    "х": "x", "Х": "X",
    "і": "i", "І": "I",
    "ј": "j", "Ј": "J",
})
_COMPACT_INJECTION_PATTERNS = [
    re.compile(r"i[g9]n[o0]r[e3](?:all|any|prior|previous){0,2}(?:instructions?|prompts?|commands?)"),
    re.compile(r"(?:reveal|show|display)(?:all|your|the)?(?:instructions?|prompts?|systemmessages?|systemprompt)"),
    re.compile(r"(?:developer|sudo)mode"),
    re.compile(r"jailbreak"),
    re.compile(r"override(?:all|previous|any)?(?:instructions?|prompts?|commands?)"),
    re.compile(r"disregard(?:all|previous|above)"),
    re.compile(r"newinstructions?"),
]


def _normalize_for_prompt_injection_detection(text: str) -> str:
    """Normalize text to detect obfuscated prompt injection phrases."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.translate(_HOMOGLYPH_TRANSLATION)
    normalized = _ZERO_WIDTH_RE.sub("", normalized)
    normalized = normalized.lower().translate(_LEET_TRANSLATION)
    return _NON_ALNUM_RE.sub("", normalized)


def _matches_compact_injection_patterns(compact_text: str) -> bool:
    """Check compacted text against robust prompt-injection indicators."""
    if not compact_text:
        return False
    return any(pattern.search(compact_text) for pattern in _COMPACT_INJECTION_PATTERNS)


def _contains_obfuscated_prompt_injection(content: str) -> bool:
    """Detect prompt injection even when obfuscated via spacing, homoglyphs, or base64."""
    compact = _normalize_for_prompt_injection_detection(content)
    if _matches_compact_injection_patterns(compact):
        return True

    # Try decoding long base64-like blobs and inspect decoded content
    for token in re.findall(r"\b[A-Za-z0-9+/]{20,}={0,2}\b", content):
        padded = token + "=" * ((4 - len(token) % 4) % 4)
        try:
            decoded = base64.b64decode(padded, validate=True).decode("utf-8", errors="ignore")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if _matches_compact_injection_patterns(_normalize_for_prompt_injection_detection(decoded)):
            return True

    return False


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

    # SECURITY FIX: URL-decode multiple times to handle encoding bypasses
    # Example: "ignore%20previous%20instructions" -> "ignore previous instructions"
    import urllib.parse
    # 1a. URL-Decode up to 3 times (handle double/triple encoding)
    # Use unquote_plus to handle '+' as space (common in form data)
    for _ in range(3):
        try:
            decoded = urllib.parse.unquote_plus(content)
            if decoded == content:
                break  # No more decoding needed
            content = decoded
        except (TypeError, ValueError, UnicodeDecodeError):
            break  # Decoding failed, continue with original

    # 1b. Unicode normalization to prevent homograph attacks
    # Example: "ⅰgnore" (unicode) -> "ignore" (ascii)
    try:
        content = unicodedata.normalize('NFKC', content)
    except (TypeError, ValueError):
        logger.debug("Unicode normalization failed during content sanitization")

    # 2. Remove dangerous prompt injection patterns (now more effective after decoding)
    dangerous_patterns = [
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
    ]

    for pattern in dangerous_patterns:
        content = re.sub(pattern, "[FILTERED_CONTENT]", content)

    # 2b. Detect obfuscated injections not covered by direct regex substitutions
    if _contains_obfuscated_prompt_injection(content):
        content = "[FILTERED_CONTENT]"

    # 3. Limit length to prevent token exhaustion
    if len(content) > max_length:
        content = content[:max_length] + "\n...[CONTENT_TRUNCATED_FOR_SAFETY]"

    # 4. Mark as external content for context separation
    return f"[EXTERNAL_WEB_CONTENT_START]\n{content}\n[EXTERNAL_WEB_CONTENT_END]"


def extract_links(html: str, base_url: str) -> List[str]:
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


def read_page(
    url: str,
    max_length: int = 8000,
    include_links: bool = True,
    smart_contact_search: bool = True,
    include_contact_info: bool = True,
) -> Optional[str]:
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

        # Extract text
        text = clean_html(response.text, max_length=max_length)
        
        # Sanitize content to prevent prompt injection attacks
        text = sanitize_crawled_content_for_llm(text, max_length=max_length)

        # Extract contact information
        if include_contact_info and smart_contact_search:
            # Use intelligent contact search
            all_contacts = search_contact_info(url, max_subpages=3)
            has_contact = all_contacts["emails"] or all_contacts["phones"]

            if has_contact:
                contact_block = "\n--- Contact Information ---\n"
                if all_contacts["emails"]:
                    # Sanitize emails to prevent XSS
                    safe_emails = [sanitize_for_output(email) for email in all_contacts["emails"]]
                    contact_block += "Email: " + ", ".join(safe_emails) + "\n"
                if all_contacts["phones"]:
                    # Sanitize phone numbers to prevent XSS
                    safe_phones = [sanitize_for_output(phone) for phone in all_contacts["phones"][:5]]
                    contact_block += "Phone: " + ", ".join(safe_phones) + "\n"
                if len(all_contacts["pages_checked"]) > 1:
                    contact_block += f"\n(Found on {len(all_contacts['pages_checked'])} pages)"
                text += "\n" + sanitize_crawled_content_for_llm(contact_block, max_length=max_length)
        elif include_contact_info:
            # Simple contact extraction
            contact_info = extract_contact_info(response.text)
            has_contact = contact_info["emails"] or contact_info["phones"]

            if has_contact:
                contact_block = "\n--- Contact Information ---\n"
                if contact_info["emails"]:
                    # Sanitize emails to prevent XSS
                    safe_emails = [sanitize_for_output(email) for email in contact_info["emails"]]
                    contact_block += "Email: " + ", ".join(safe_emails) + "\n"
                if contact_info["phones"]:
                    # Sanitize phone numbers to prevent XSS
                    safe_phones = [sanitize_for_output(phone) for phone in contact_info["phones"][:3]]
                    contact_block += "Phone: " + ", ".join(safe_phones) + "\n"
                text += "\n" + sanitize_crawled_content_for_llm(contact_block, max_length=max_length)

        # Extract links if requested
        if include_links:
            links = extract_links(response.text, url)
            if links:
                # Highlight contact pages
                contact_pages = find_contact_pages(links)
                if contact_pages:
                    links_block = f"\n--- Contact Subpages ({len(contact_pages)}) ---\n"
                    # Sanitize URLs to prevent XSS in links
                    safe_contact_pages = [sanitize_for_output(link) for link in contact_pages[:10]]
                    links_block += "\n".join(f"- {link}" for link in safe_contact_pages)
                    text += "\n" + sanitize_crawled_content_for_llm(links_block, max_length=max_length)

                # Show other pages
                other_pages = [l for l in links if l not in contact_pages]
                if other_pages:
                    other_block = f"\n--- Additional Subpages ({len(other_pages)}) ---\n"
                    # Sanitize URLs to prevent XSS in links
                    safe_other_pages = [sanitize_for_output(link) for link in other_pages[:15]]
                    other_block += "\n".join(f"- {link}" for link in safe_other_pages)
                    if len(other_pages) > 15:
                        other_block += f"\n... and {len(other_pages) - 15} more"
                    text += "\n" + sanitize_crawled_content_for_llm(other_block, max_length=max_length)

        logger.info(f"Extracted {len(text)} characters from page")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
        return text

    except requests.RequestException as e:
        logger.error(f"Failed to read page: {e}")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
        return None
    except Exception as e:
        logger.error(f"Unexpected error reading page: {e}")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
        return None


def extract_main_content(html: str) -> Optional[str]:
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

    except Exception as e:
        logger.error("Failed to extract metadata from page: error occurred")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
        return {"url": "REDACTED", "title": "", "description": "", "keywords": []}
