"""Security validators and input sanitization."""
import re
import logging
from typing import List, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

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


def sanitize_query(query: str) -> str:
    """
    Sanitize and validate user query input.

    Args:
        query: User query to sanitize

    Returns:
        Sanitized query string

    Raises:
        ValueError: If query contains suspicious patterns
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    # Strip whitespace
    sanitized = query.strip()

    # Check for suspicious patterns
    suspicious = [
        r"<script",
        r"javascript:",
        r"eval\(",
        r"exec\(",
        r"__import__"
    ]

    for pattern in suspicious:
        if re.search(pattern, sanitized, re.IGNORECASE):
            logger.warning(f"Suspicious pattern in query: {pattern}")
            raise ValueError(f"Query contains forbidden pattern: {pattern}")

    return sanitized


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


def sanitize_url_for_logging(url: str) -> str:
    """
    Sanitize URL for safe logging by removing sensitive query parameters.

    This prevents logging of API keys, tokens, and other secrets that might
    be present in URL query parameters.

    Args:
        url: Original URL that may contain sensitive data

    Returns:
        Sanitized URL safe for logging

    Examples:
        >>> sanitize_url_for_logging("https://api.example.com?key=secret123")
        'https://api.example.com?key=***REDACTED***'
        >>> sanitize_url_for_logging("https://example.com/path")
        'https://example.com/path'
    """
    try:
        parsed = urlparse(url)

        # If no query string, return as-is
        if not parsed.query:
            return url

        # Parse query parameters
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Sensitive parameter patterns (case-insensitive)
        sensitive_patterns = [
            'key', 'apikey', 'api_key', 'token', 'access_token',
            'secret', 'password', 'pwd', 'pass', 'auth', 'authorization',
            'credential', 'private', 'session', 'sid', 'jwt'
        ]

        # Redact sensitive parameters
        sanitized_params = {}
        for key, values in params.items():
            # Check if parameter name matches sensitive pattern
            is_sensitive = any(pattern in key.lower() for pattern in sensitive_patterns)

            if is_sensitive:
                # Redact the value but keep parameter name
                sanitized_params[key] = ['***REDACTED***'] * len(values)
            else:
                sanitized_params[key] = values

        # Rebuild query string
        sanitized_query = urlencode(sanitized_params, doseq=True)

        # Rebuild URL
        sanitized_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            sanitized_query,
            parsed.fragment
        ))

        return sanitized_url

    except Exception as e:
        # If parsing fails, return a safe placeholder
        logger.debug(f"Failed to sanitize URL: {e}")
        return "[URL parsing failed - redacted for security]"
