"""Text cleaning and processing utilities."""
import re
from typing import Optional
from bs4 import BeautifulSoup


def clean_html(html: str, max_length: Optional[int] = 3000) -> str:
    """
    Extract clean text from HTML, removing scripts, styles, and navigation.

    Args:
        html: Raw HTML content
        max_length: Maximum length of output text

    Returns:
        Cleaned text content
    """
    soup = BeautifulSoup(html, "html5lib")

    # Remove unwanted tags
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    # Extract relevant text elements
    texts = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "article"]):
        text = tag.get_text(strip=True)
        # Only include meaningful text (min 20 characters)
        if len(text) > 20:
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
