"""FastAPI auth and rate-limiting dependencies.

Extracted from ``app.py`` so endpoint routers can depend on them without
importing the app module. The manager singletons are fetched via their
``get_*`` accessors, so these are the same instances the rest of the app uses.
The in-memory rate-limit / auth-failure state lives here because only these
dependencies touch it (the Redis-backed limiter is a separate middleware).
"""
import asyncio
import hmac
import logging
import time

from fastapi import Depends, Header, HTTPException, Request, status

from api.security_config import (
    API_KEY,
    AUTH_FAILURE_LIMIT,
    RATE_LIMIT,
    _dev_bypass_allowed,
    client_ip,
    hash_api_key_for_logging,
)
from core.api_key_manager import get_api_key_manager
from core.csrf_manager import get_csrf_manager
from core.rbac_manager import Role, get_rbac_manager

logger = logging.getLogger("crawllama")

csrf_manager = get_csrf_manager()
rbac_manager = get_rbac_manager()
api_key_manager = get_api_key_manager()

# Rate limiting (simple in-memory, use Redis for production)
request_counts: dict[str, list[float]] = {}
# Async lock prevents anyio/threadpool deadlocks in ASGI test environments.
rate_limit_lock = asyncio.Lock()
auth_failure_counts: dict[str, list[float]] = {}


async def _auth_failure_budget_ok(ip_address: str) -> bool:
    """Return False when this IP has exhausted its failed-auth budget for the window.

    Sliding 1-minute window. 429 responses are NOT counted as new failures, so a
    throttled IP recovers automatically once its recent failures age out.
    """
    now = time.time()
    async with rate_limit_lock:
        # Bound memory: drop IPs with no recent failures.
        if len(auth_failure_counts) > 1024:
            for k in [k for k, ts in auth_failure_counts.items()
                      if not ts or now - ts[-1] >= 60]:
                del auth_failure_counts[k]
        recent = [t for t in auth_failure_counts.get(ip_address, []) if now - t < 60]
        auth_failure_counts[ip_address] = recent
        return len(recent) < AUTH_FAILURE_LIMIT


async def _record_auth_failure(ip_address: str) -> None:
    """Record one failed authentication attempt for this IP (sliding window)."""
    now = time.time()
    async with rate_limit_lock:
        auth_failure_counts.setdefault(ip_address, []).append(now)


def _is_bootstrap_key(api_key: str) -> bool:
    """Constant-time check against the bootstrap key (bytes: non-ASCII safe)."""
    return hmac.compare_digest(api_key.encode("utf-8"), API_KEY.encode("utf-8"))


def principal_for_key(api_key: str) -> str:
    """Return the principal (RBAC/ownership identity) an API key acts for.

    The bootstrap key and unknown keys map to their own keyed hash; an active
    managed key maps to the ``user_id`` it was issued to.
    """
    if not _is_bootstrap_key(api_key):
        try:
            is_valid, owner_id = api_key_manager.validate_key(api_key)
        except Exception:
            logger.error("API key validation backend error", exc_info=True)
            is_valid, owner_id = False, None
        if is_valid and owner_id:
            return owner_id
    return hash_api_key_for_logging(api_key)


async def verify_api_key(request: Request, x_api_key: str | None = Header(None)):
    """Verify API key for authentication.

    Accepts two kinds of credentials:

    1. The bootstrap key (``CRAWLLAMA_API_KEY``), compared in constant time.
    2. Any active, non-expired key issued through the rotation-capable
       :class:`APIKeyManager` (``/admin/api-keys/*``).

    Returns the authenticated plaintext key (needed for rotation/revocation)
    and stores the principal it acts for in ``request.state.principal_id``
    (read it through the :func:`get_principal_id` dependency).
    """
    # Skip API key check in DEV_MODE — but only for loopback clients
    if _dev_bypass_allowed(request):
        request.state.principal_id = hash_api_key_for_logging("dev")
        return "dev"

    ip_address = client_ip(request)

    # SECURITY: throttle brute-force. If this IP has already burned its failed-auth
    # budget this minute, reject early — before the storage-backed validate_key()
    # lookup — so invalid keys cannot be sprayed unboundedly.
    if not await _auth_failure_budget_ok(ip_address):
        logger.warning("Authentication failure rate limit exceeded")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed authentication attempts. Try again later.",
        )

    if not x_api_key:
        await _record_auth_failure(ip_address)
        logger.warning("Missing API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # 1. Constant-time comparison against the bootstrap key (prevents timing
    #    side-channel recovery of the shared secret).
    #    Compare bytes: compare_digest raises TypeError on non-ASCII str input.
    if _is_bootstrap_key(x_api_key):
        request.state.principal_id = hash_api_key_for_logging(x_api_key)
        return x_api_key

    # 2. Validate against the rotation manager (multi-key, expiry, revocation).
    try:
        is_valid, owner_id = api_key_manager.validate_key(x_api_key)
    except Exception:
        # Storage-backend error: fail closed rather than granting access.
        logger.error("API key validation backend error", exc_info=True)
        is_valid, owner_id = False, None

    if is_valid:
        # Managed keys act for the principal they were issued to, so roles and
        # key ownership follow the owner instead of each individual key.
        request.state.principal_id = owner_id or hash_api_key_for_logging(x_api_key)
        return x_api_key

    # SECURITY: Never log API keys - only log that authentication failed
    await _record_auth_failure(ip_address)
    logger.warning("Invalid or missing API key attempt")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )


def verify_csrf_token(
    request: Request,
    x_csrf_token: str | None = Header(None),
    api_key: str = Depends(verify_api_key)
) -> str:
    """Verify CSRF token for state-changing operations.
    
    Args:
        x_csrf_token: CSRF token from X-CSRF-Token header
        api_key: Authenticated API key
        
    Returns:
        The validated CSRF token
        
    Raises:
        HTTPException: If CSRF token is invalid or missing
    """
    # Skip in DEV_MODE — but only for loopback clients
    if _dev_bypass_allowed(request):
        return "dev"

    if not x_csrf_token:
        logger.warning("CSRF token missing in request")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token required for this operation. Get token from /csrf-token endpoint."
        )
    
    # Use hashed API key as user ID for CSRF validation
    user_id = hash_api_key_for_logging(api_key)
    
    # Validate token
    if not csrf_manager.validate_token(user_id, x_csrf_token):
        logger.warning("Invalid CSRF token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired CSRF token. Request a new token from /csrf-token endpoint."
        )
    
    return x_csrf_token


def verify_role(required_role: Role):
    """Create a dependency that verifies user has required role.
    
    Args:
        required_role: Minimum role required for access
        
    Returns:
        A FastAPI dependency function
    """
    def role_checker(request: Request, api_key: str = Depends(verify_api_key)) -> str:
        """Check if user has required role.
        
        Args:
            api_key: Authenticated API key
            
        Returns:
            The API key if authorized
            
        Raises:
            HTTPException: If user lacks required permissions
        """
        # Skip in DEV_MODE — but only for loopback clients
        if _dev_bypass_allowed(request):
            return api_key

        # Get the role of the principal this key acts for
        user_id = get_principal_id(request, api_key)
        user_role = rbac_manager.get_role(user_id)
        
        # Check permission
        if not rbac_manager.check_permission(user_id, required_role):
            logger.warning(
                f"Access denied: user role {user_role.value} "
                f"attempted to access {required_role.value}-only endpoint"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. This endpoint requires {required_role.value} role. "
                       f"Your role: {user_role.value}"
            )
        
        return api_key
    
    return role_checker


async def check_rate_limit(request: Request, api_key: str = Depends(verify_api_key)):
    """Rate limiting based on API key or IP."""
    # Use API key if available, otherwise use IP
    if api_key != "dev":
        key = api_key
    else:
        # Fallback to IP address, or "unknown" if not available
        key = client_ip(request)
    current_time = time.time()

    # Thread-safe rate limiting
    async with rate_limit_lock:
        # Prune stale keys occasionally so the dict cannot grow unbounded
        # (an attacker rotating API keys/IPs would otherwise leak memory).
        if len(request_counts) > 1024:
            stale = [
                k for k, stamps in request_counts.items()
                if not stamps or current_time - stamps[-1] >= 60
            ]
            for k in stale:
                del request_counts[k]

        if key not in request_counts:
            request_counts[key] = []

        # Remove old requests (older than 1 minute)
        request_counts[key] = [
            ts for ts in request_counts[key]
            if current_time - ts < 60
        ]

        if len(request_counts[key]) >= RATE_LIMIT:
            # SECURITY: Hash API key before logging to prevent exposure
            # lgtm[py/clear-text-logging-sensitive-data] - API key is hashed before logging
            logger.warning("Rate limit exceeded for API key")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {RATE_LIMIT} requests per minute."
            )

        request_counts[key].append(current_time)

    return key


def get_principal_id(request: Request, api_key: str = Depends(verify_api_key)) -> str:
    """Dependency: the principal the authenticated key acts for (see verify_api_key)."""
    principal_id = getattr(request.state, "principal_id", None)
    return principal_id or principal_for_key(api_key)
