"""Security validators and input sanitization."""
import re
import logging
from typing import List, Optional
from urllib.parse import urlparse

logger = logging.getLogger("crawllama")

# Dangerous patterns to detect in LLM outputs
DANGEROUS_PATTERNS = [
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__",
    r"<script[^>]*>",
    r"javascript:",
    r"on\w+\s*=",  # Event handlers like onclick=
]

# Allowed URL schemes
ALLOWED_SCHEMES = ["http", "https"]


def is_safe_url(url: str, allowed_domains: Optional[List[str]] = None) -> bool:
    """
    Validate URL for security.

    Args:
        url: URL to validate
        allowed_domains: Optional whitelist of allowed domains

    Returns:
        True if URL is safe, False otherwise
    """
    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ALLOWED_SCHEMES:
            logger.warning(f"Invalid URL scheme: {parsed.scheme}")
            return False

        # Check for localhost/private IPs (basic protection)
        hostname = parsed.hostname
        if hostname:
            if hostname in ["localhost", "127.0.0.1", "0.0.0.0"]:
                logger.warning(f"Localhost/private IP not allowed: {hostname}")
                return False

            # Check private IP ranges
            if hostname.startswith(("192.168.", "10.", "172.16.")):
                logger.warning(f"Private IP range not allowed: {hostname}")
                return False

        # Whitelist check (if configured)
        if allowed_domains and parsed.netloc not in allowed_domains:
            logger.warning(f"Domain not in whitelist: {parsed.netloc}")
            return False

        return True

    except Exception as e:
        logger.error(f"URL validation error: {e}")
        return False


def sanitize_llm_output(text: str) -> str:
    """
    Sanitize LLM output by detecting potentially dangerous patterns.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text

    Raises:
        ValueError: If dangerous pattern is detected
    """
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger.error(f"Dangerous pattern detected: {pattern}")
            raise ValueError(f"Dangerous pattern detected: {pattern}")

    return text


def validate_query(query: str, max_length: int = 500) -> bool:
    """
    Validate user query input.

    Args:
        query: User query to validate
        max_length: Maximum allowed length

    Returns:
        True if valid, False otherwise
    """
    if not query or not query.strip():
        logger.warning("Empty query")
        return False

    if len(query) > max_length:
        logger.warning(f"Query too long: {len(query)} > {max_length}")
        return False

    # Check for suspicious patterns
    suspicious = [
        r"<script",
        r"javascript:",
        r"eval\(",
        r"exec\("
    ]

    for pattern in suspicious:
        if re.search(pattern, query, re.IGNORECASE):
            logger.warning(f"Suspicious pattern in query: {pattern}")
            return False

    return True


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal attacks.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove path separators and special characters
    sanitized = re.sub(r'[^\w\s.-]', '', filename)
    sanitized = sanitized.replace("..", "")
    sanitized = sanitized.strip()

    if not sanitized:
        sanitized = "unnamed_file"

    return sanitized
