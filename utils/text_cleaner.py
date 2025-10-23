"""Text cleaning and processing utilities."""
import re
from typing import Optional
from bs4 import BeautifulSoup


def extract_contact_info(html: str) -> dict:
    """
    Extract contact information from HTML.

    Args:
        html: Raw HTML content

    Returns:
        Dictionary with contact info (emails, phones, addresses)
    """
    soup = BeautifulSoup(html, "html5lib")
    text = soup.get_text()

    contact_info = {
        "emails": [],
        "phones": [],
        "addresses": []
    }

    # Extract emails
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    contact_info["emails"] = list(set(emails))

    # Extract phone numbers (various formats)
    phone_patterns = [
        r'\+?\d{1,4}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\d{4,5}[-.\s]?\d{4,}'
    ]
    phones = []
    for pattern in phone_patterns:
        phones.extend(re.findall(pattern, text))
    # Filter valid phone numbers (minimum 6 digits)
    contact_info["phones"] = [p for p in set(phones) if len(re.sub(r'\D', '', p)) >= 6]

    return contact_info


def clean_html(html: str, max_length: Optional[int] = 8000) -> str:
    """
    Extract clean text from HTML, removing scripts and styles but preserving content.

    Args:
        html: Raw HTML content
        max_length: Maximum length of output text (default 8000)

    Returns:
        Cleaned text content
    """
    soup = BeautifulSoup(html, "html5lib")

    # Remove only scripts and styles (keep footer, header for contact info)
    for tag in soup(["script", "style", "nav", "aside"]):
        tag.decompose()

    # Extract relevant text elements including footer/header
    texts = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "article", "footer", "header", "address", "div"]):
        text = tag.get_text(strip=True)
        # Only include meaningful text (min 15 characters, reduced from 20)
        if len(text) > 15:
            texts.append(text)

    # Combine texts
    combined = "\n".join(texts)

    # Clean up whitespace
    combined = re.sub(r'\s+', ' ', combined)
    combined = combined.strip()

    # Truncate if needed
    if max_length and len(combined) > max_length:
        combined = combined[:max_length] + "..."

    return combined


def truncate_text(text: str, max_chars: int = 1000, ellipsis: str = "...") -> str:
    """
    Truncate text to maximum length, breaking at word boundaries.

    Args:
        text: Text to truncate
        max_chars: Maximum number of characters
        ellipsis: Ellipsis to append if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_chars:
        return text

    # Find last space before max_chars
    truncated = text[:max_chars]
    last_space = truncated.rfind(' ')

    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated + ellipsis


def clean_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)

    # Replace multiple newlines with double newline
    text = re.sub(r'\n\s*\n+', '\n\n', text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def extract_urls(text: str) -> list:
    """
    Extract URLs from text.

    Args:
        text: Text containing URLs

    Returns:
        List of extracted URLs
    """
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(url_pattern, text)


def remove_urls(text: str) -> str:
    """
    Remove URLs from text.

    Args:
        text: Text containing URLs

    Returns:
        Text with URLs removed
    """
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.sub(url_pattern, '', text)
