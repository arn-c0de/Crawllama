"""Security configuration and stateless auth helpers for the API.

Holds the session-scoped secrets (API key, rate-limit HMAC secret), the
request-limit tunables and the small, stateless helpers used by the auth /
rate-limit dependencies and middleware. Extracted from ``app.py`` so routers
and dependencies can import them without reaching back into the app module.
"""
import ipaddress
import logging
import os
import secrets

from fastapi import Request

from utils.secure_hash import hmac_sha256_hex

logger = logging.getLogger("crawllama")


def is_dev_mode() -> bool:
    """Return True when CRAWLLAMA_DEV_MODE is enabled (relaxed security for local development)."""
    return os.getenv("CRAWLLAMA_DEV_MODE", "false").lower() == "true"


# Security: Load API key from environment or generate temporary one
API_KEY = os.getenv("CRAWLLAMA_API_KEY", None)
if not API_KEY:
    API_KEY = secrets.token_urlsafe(32)
    # SECURITY: Never log the actual API key - only indicate one was generated
    logger.warning("No API_KEY set in environment. Generated temporary key for this session.")
    logger.warning("IMPORTANT: Set CRAWLLAMA_API_KEY in .env for production!")
    logger.warning("Retrieve the temporary key via /dev/api-key endpoint (only available in DEV_MODE)")

# Security: HMAC secret for rate limiting (cryptographically secure hashing)
RATE_LIMIT_SECRET = os.getenv("RATE_LIMIT_SECRET", None)
# Track whether the secret is ephemeral (regenerated each start). An ephemeral
# secret silently invalidates all previously issued managed API-key hashes after
# a restart, so it must never be used in production (enforced at startup below).
RATE_LIMIT_SECRET_EPHEMERAL = not RATE_LIMIT_SECRET
if not RATE_LIMIT_SECRET:
    RATE_LIMIT_SECRET = secrets.token_bytes(32)  # 256-bit secret
    logger.warning("No RATE_LIMIT_SECRET set. Generated temporary secret for this session.")
    logger.warning("Set RATE_LIMIT_SECRET in .env for consistent rate limiting across restarts.")
elif isinstance(RATE_LIMIT_SECRET, str):
    # Convert string to bytes if loaded from env
    RATE_LIMIT_SECRET = RATE_LIMIT_SECRET.encode('utf-8')

RATE_LIMIT = int(os.getenv("RATE_LIMIT", "60"))  # requests per minute
# Per-IP cap on FAILED authentication attempts per minute. Unlike the per-principal
# limiter above (which only counts authenticated callers), this throttles unauthenticated
# invalid-key requests to bound credential brute-forcing and the storage lookups they cause.
AUTH_FAILURE_LIMIT = int(os.getenv("AUTH_FAILURE_LIMIT", "20"))


def _is_loopback_host(host: str) -> bool:
    """Return True only for loopback bind addresses (127.0.0.0/8, ::1, localhost)."""
    h = (host or "").strip().lower()
    if h == "localhost":
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        # Any other hostname (or 0.0.0.0/:: which are non-loopback) is treated
        # as network-reachable.
        return False


def _dev_bypass_allowed(request: Request | None) -> bool:
    """Whether DEV_MODE's auth/CSRF/RBAC bypass may apply to THIS request.

    SECURITY (defence-in-depth): the startup guard (`_enforce_dev_mode_loopback_only`)
    only sees the *env-configured* bind host, so it cannot catch a launch like
    `uvicorn app:app --host 0.0.0.0`. To close that gap, the DEV_MODE relaxations
    are additionally gated per-request on the client being loopback. A remote
    client always gets the full auth/CSRF/RBAC stack even if DEV_MODE is on.
    """
    if not is_dev_mode():
        return False
    if request is None or request.client is None:
        return False
    return _is_loopback_host(request.client.host)


def hash_api_key_for_logging(key: str) -> str:
    """
    Hash API key for secure logging.

    Uses HMAC-SHA256 truncated to 16 characters to prevent key exposure in logs
    while maintaining uniqueness for debugging purposes.
    HMAC provides cryptographic security against length extension attacks.

    Args:
        key: The API key to hash

    Returns:
        Hashed key (16 hex chars) or original if it's a special value
    """
    # Don't hash special values. Return the matched literal rather than the
    # input so no code path can ever propagate the raw key to a caller.
    if key == "unknown":
        return "unknown"
    if key == "dev":
        return "dev"

    # Don't hash IP addresses (both IPv4 and IPv6). Return the canonical form
    # rebuilt from the parsed address, again never the raw input string.
    try:
        return str(ipaddress.ip_address(key))
    except ValueError:
        pass  # Not an IP address, proceed with hashing

    # SECURITY: Use a keyed HMAC (default SHA3-256) to derive a stable
    # identifier for logging while preventing reversal of sensitive keys.
    # The key is immediately hashed with a secret and never stored/logged in plaintext
    return hmac_sha256_hex(key, key=RATE_LIMIT_SECRET)  # deterministic, keyed ID


def _short_id(value: str) -> str:
    """Truncate an identifier/hash to a short, log-safe display form."""
    return f"{value[:16]}..."


def client_ip(request: Request, default: str = "unknown") -> str:
    """Return the direct client's IP address, or ``default`` if unknown."""
    return request.client.host if request.client else default


def _rate_limit_user_id(request: Request) -> str:
    """Derive a stable, non-reversible rate-limiting identifier (API key hash or client IP)."""
    api_key = request.headers.get("X-API-Key", "")
    if not api_key or api_key == "dev" or is_dev_mode():
        return client_ip(request)
    # SECURITY: Use a keyed HMAC (default SHA3-256) to derive a stable
    # identifier for rate limiting while preventing reversal of API keys.
    # The API key is immediately hashed with a secret key and never stored/logged in plaintext
    # This is the CORRECT way to handle API keys for rate limiting (not password storage)
    return hmac_sha256_hex(api_key, key=RATE_LIMIT_SECRET)  # deterministic, keyed ID
