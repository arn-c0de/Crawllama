"""Security validators and input sanitization."""
import re
import logging
import socket
import time
from typing import List, Optional, Tuple
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
    Validate URL for security (basic SSRF protection).
    
    NOTE: This function only performs basic validation. For full SSRF protection 
    including DNS rebinding detection, use validate_url_ssrf_safe() instead.

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

        # Check for localhost/private IPs (security enhancement)
        hostname = parsed.hostname
        if hostname:
            import ipaddress
            try:
                ip_obj = ipaddress.ip_address(hostname)
                if ip_obj.is_unspecified:
                    logger.warning(f"Unspecified address (binding to all interfaces) is not allowed: {hostname}")
                    return False
                if ip_obj.is_loopback:
                    logger.warning(f"Loopback address is not allowed: {hostname}")
                    return False
                if ip_obj.is_private:
                    logger.warning(f"Private IP address is not allowed: {hostname}")
                    return False
            except ValueError:
                # Not an IP address, check for localhost
                if hostname.lower() == "localhost":
                    logger.warning(f"Localhost is not allowed: {hostname}")
                    return False

        # Whitelist check (if configured)
        if allowed_domains and parsed.netloc not in allowed_domains:
            logger.warning(f"Domain not in whitelist: {parsed.netloc}")
            return False

        return True

    except Exception as e:
        logger.error(f"URL validation error: {e}")
        return False


def validate_url_ssrf_safe(
    url: str, 
    allowed_domains: Optional[List[str]] = None,
    check_dns_rebinding: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Enhanced SSRF protection with DNS rebinding detection.
    
    Performs comprehensive validation to prevent Server-Side Request Forgery attacks:
    1. Validates URL scheme (only http/https allowed)
    2. Resolves hostname to IP addresses
    3. Checks all resolved IPs against dangerous ranges
    4. Optionally performs DNS rebinding detection (double-check with delay)
    
    Args:
        url: URL to validate
        allowed_domains: Optional list of allowed domains (e.g., ['example.com'])
        check_dns_rebinding: If True, performs DNS rebinding detection (100ms delay)
        
    Returns:
        Tuple of (is_safe: bool, error_message: Optional[str])
        - (True, None) if URL is safe
        - (False, "error reason") if URL is dangerous
        
    Example:
        >>> is_safe, error = validate_url_ssrf_safe("http://example.com/api")
        >>> if not is_safe:
        ...     raise SecurityError(f"SSRF detected: {error}")
    """
    try:
        parsed = urlparse(url)

        # Only allow http/https
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False, f"Blocked non-HTTP(S) scheme: {parsed.scheme}"

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL: no hostname"

        # Check allowed domains first (fail fast)
        if allowed_domains:
            if not any(hostname.endswith(domain) for domain in allowed_domains):
                return False, f"Domain '{hostname}' not in allowlist"

        # Resolve DNS and validate IPs (first check)
        is_safe, error = _validate_hostname_ips(hostname, url)
        if not is_safe:
            return False, error

        # DNS rebinding detection: wait 100ms and check again
        if check_dns_rebinding:
            time.sleep(0.1)  # 100ms delay
            is_safe_second, error_second = _validate_hostname_ips(hostname, url)
            if not is_safe_second:
                return False, f"DNS rebinding detected: {error_second}"

        return True, None

    except Exception as e:
        # SECURITY: Sanitize exception message to avoid logging sensitive URLs
        sanitized_error = sanitize_exception_message(str(e))
        logger.error(f"Error validating URL: {sanitized_error}", exc_info=True)  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted to avoid logging details
        return False, f"Validation error: {sanitized_error}"


def _validate_hostname_ips(hostname: str, url: str) -> Tuple[bool, Optional[str]]:
    """
    Internal helper: Resolve hostname and validate all IPs are safe.
    
    Args:
        hostname: Hostname to resolve
        url: Original URL (for logging)
        
    Returns:
        Tuple of (is_safe: bool, error_message: Optional[str])
    """
    import ipaddress

    # Block common localhost names
    if hostname.lower() in ['localhost', 'broadcasthost']:
        return False, f"Blocked localhost name: {hostname}"

    # Resolve hostname to IP addresses
    try:
        # getaddrinfo returns list of (family, type, proto, canonname, sockaddr)
        addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        
        if not addr_infos:
            return False, f"DNS resolution failed: no addresses for {hostname}"

        # Check every resolved IP address
        for family, _, _, _, sockaddr in addr_infos:
            ip_str = sockaddr[0]  # Extract IP from sockaddr tuple
            
            try:
                ip = ipaddress.ip_address(ip_str)
                
                # Check specific ranges BEFORE general categories
                # Block special IPv4 ranges (specific checks first)
                if isinstance(ip, ipaddress.IPv4Address):
                    # 169.254.0.0/16 (link-local, AWS metadata)
                    if ip in ipaddress.IPv4Network('169.254.0.0/16'):
                        return False, f"Blocked AWS metadata IP: {ip_str}"
                    # 0.0.0.0/8 (current network)
                    if ip in ipaddress.IPv4Network('0.0.0.0/8'):
                        return False, f"Blocked current network IP: {ip_str}"
                    # 192.0.0.0/24 (IETF protocol assignments)
                    if ip in ipaddress.IPv4Network('192.0.0.0/24'):
                        return False, f"Blocked IETF protocol IP: {ip_str}"
                
                # Block special IPv6 ranges (specific checks first)
                if isinstance(ip, ipaddress.IPv6Address):
                    # fc00::/7 (unique local)
                    if ip in ipaddress.IPv6Network('fc00::/7'):
                        return False, f"Blocked unique local IPv6: {ip_str}"
                
                # Block dangerous IP ranges (general categories)
                if ip.is_loopback:
                    return False, f"Blocked loopback IP: {ip_str} (resolves from {hostname})"
                if ip.is_link_local:
                    return False, f"Blocked link-local IP: {ip_str} (resolves from {hostname})"
                if ip.is_unspecified:
                    return False, f"Blocked unspecified IP: {ip_str} (resolves from {hostname})"
                if ip.is_private:
                    return False, f"Blocked private IP: {ip_str} (resolves from {hostname})"
                if ip.is_multicast:
                    return False, f"Blocked multicast IP: {ip_str} (resolves from {hostname})"
                if ip.is_reserved:
                    return False, f"Blocked reserved IP: {ip_str} (resolves from {hostname})"

            except ValueError as ve:
                logger.warning(f"Could not parse IP {ip_str}: {ve}")
                return False, f"Invalid IP address: {ip_str}"

        # All IPs are safe
        return True, None

    except socket.gaierror as e:
        # DNS resolution failed
        logger.warning(f"DNS resolution failed for {sanitize_for_logging(hostname, 'domain')}: {sanitize_exception_message(str(e))}")
        return False, f"DNS resolution failed: {sanitize_for_logging(hostname, 'domain')}"
    except OSError as e:
        logger.error(f"OS error resolving {sanitize_for_logging(hostname, 'domain')}: {sanitize_exception_message(str(e))}")
        return False, f"Network error: {sanitize_exception_message(str(e))}"


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


def sanitize_for_logging(value: str, value_type: str = 'generic') -> str:
    """
    Sanitize sensitive data for safe logging.

    This function masks sensitive information to prevent exposure in logs
    while still providing enough context for debugging.

    Args:
        value: The sensitive value to sanitize
        value_type: Type of value ('domain', 'user_id', 'email', 'generic')

    Returns:
        Sanitized value safe for logging

    Examples:
        >>> sanitize_for_logging("example.com", "domain")
        'exa***'
        >>> sanitize_for_logging("user123", "user_id")
        'use***'
        >>> sanitize_for_logging("sensitive@example.com", "email")
        's***@e***'
    """
    if not value or not isinstance(value, str):
        return "[empty]"

    value = value.strip()

    if len(value) <= 3:
        return "***"

    if value_type == 'domain':
        # For domains, show first 3 chars
        return f"{value[:3]}***"
    elif value_type == 'email':
        # For emails, show first char of username and domain
        if '@' in value:
            username, domain = value.split('@', 1)
            return f"{username[0]}***@{domain[0] if domain else ''}***"
        return f"{value[0]}***"
    elif value_type == 'user_id':
        # For user IDs, show first 3 chars
        return f"{value[:3]}***"
    else:
        # Generic: show first 3 chars
        return f"{value[:3]}***"


def sanitize_exception_message(message: str) -> str:
    """
    Sanitize exception message by redacting URLs that may contain sensitive data.

    Args:
        message: Original exception message

    Returns:
        Sanitized message with URLs redacted
    """
    import re
    
    # Find all URLs in the message
    url_pattern = r'https?://[^\s<>"\']+' 
    
    def replace_url(match):
        url = match.group(0)
        return sanitize_url_for_logging(url)
    
    # Replace all URLs with sanitized versions
    sanitized = re.sub(url_pattern, replace_url, message)
    return sanitized


def sanitize_for_log_injection(text: str, max_length: int = 200) -> str:
    """
    Sanitize user input to prevent log injection attacks.
    
    Removes or replaces characters that could be used for log injection:
    - Newlines (\n, \r)
    - Control characters
    - Null bytes
    - ANSI escape sequences
    
    Args:
        text: Text to sanitize
        max_length: Maximum length (truncate if longer)
    
    Returns:
        Sanitized text safe for logging
    """
    if not text or not isinstance(text, str):
        return ""
    
    import re
    
    # Remove control characters and newlines
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Remove ANSI escape sequences
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text
