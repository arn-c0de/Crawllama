"""HTTP middleware stack of the CrawlLama API (security headers, CSRF, audit, rate limit)."""
import logging
import os
import sys
import time

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from api import runtime
from api.security_config import _dev_bypass_allowed, _rate_limit_user_id, _short_id, client_ip, hash_api_key_for_logging
from core.audit_logger import get_audit_logger
from core.csrf_manager import validate_origin_header, validate_referer_header
from utils.redis_rate_limiter import get_rate_limit_for_endpoint

logger = logging.getLogger("crawllama")

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
)


def allowed_hosts_from_env() -> list[str]:
    """Allowed Host header values (ALLOWED_HOSTS; no wildcard by default).

    0.0.0.0 is a bind address, never a valid Host header value, so it is not
    an allowed host here.
    """
    allowed_hosts = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
    # Add testserver only for the in-process test client (Starlette TestClient uses
    # Host: testserver). Never enabled outside an explicit test environment.
    if os.getenv("CRAWLLAMA_TESTING", "false").lower() == "true" or "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules:
        allowed_hosts.append("testserver")
    return allowed_hosts


def cors_origins_from_env() -> list[str]:
    """CORS origins from ALLOWED_ORIGINS (SECURITY: no wildcard, explicit in production)."""
    cors_origins_env = os.getenv("ALLOWED_ORIGINS", "")
    if cors_origins_env:
        # Strip whitespace so " https://app.example" entries still match, and drop empties.
        cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
        # SECURITY: a credentialed wildcard ("*" with allow_credentials=True) lets any
        # site read authenticated responses. Refuse it and fall back to safe defaults.
        if "*" in cors_origins:
            logger.error(
                "ALLOWED_ORIGINS contains '*', which is unsafe with credentialed CORS. "
                "Ignoring the wildcard and using restrictive localhost defaults instead."
            )
            cors_origins = [o for o in cors_origins if o != "*"]
        if not cors_origins:
            cors_origins = list(DEFAULT_CORS_ORIGINS)
    else:
        # Development default - restrictive
        cors_origins = list(DEFAULT_CORS_ORIGINS)
        logger.warning("No ALLOWED_ORIGINS set. Using development defaults. Set ALLOWED_ORIGINS for production!")
    return cors_origins


# Paths exempt from rate limiting and audit logging (public docs/health endpoints)
PUBLIC_PATHS = frozenset({"/health", "/", "/docs", "/redoc", "/openapi.json"})
# Paths exempt from CSRF Origin/Referer validation
CSRF_EXEMPT_PATHS = PUBLIC_PATHS | {"/csrf-token"}


# Security Headers Middleware
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Content Security Policy - Prevent XSS attacks
    # Strengthened CSP with stricter policies
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "  # Removed 'unsafe-inline' for better XSS protection
        "style-src 'self' 'unsafe-inline'; "  # Still needed for inline styles
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "object-src 'none'; "  # Block plugins
        "base-uri 'self'; "  # Prevent base tag injection
        "form-action 'self'; "  # Restrict form submissions
        "frame-ancestors 'none'; "  # Prevent clickjacking
        "upgrade-insecure-requests;"  # Upgrade HTTP to HTTPS
    )
    
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # XSS Protection (legacy but still useful)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Referrer Policy - Control information leakage
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions Policy - Disable unnecessary browser features
    response.headers["Permissions-Policy"] = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=()"
    )
    
    # HSTS - Force HTTPS (only in production with HTTPS)
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    
    return response


# CSRF Origin/Referer Validation Middleware
async def csrf_origin_referer_middleware(request: Request, call_next):
    """
    Validate Origin and Referer headers for state-changing requests.
    
    Provides CSRF protection by ensuring requests originate from trusted sources.
    Only applies to POST, PUT, PATCH, DELETE methods.
    """
    # Skip for safe methods (GET, HEAD, OPTIONS)
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return await call_next(request)
    
    # Skip for public endpoints and dev endpoints
    if request.url.path in CSRF_EXEMPT_PATHS:
        return await call_next(request)

    # Skip in DEV_MODE — but only for loopback clients (see _dev_bypass_allowed)
    if _dev_bypass_allowed(request):
        return await call_next(request)

    # Validate Origin header (preferred)
    origin = request.headers.get("Origin")
    if origin:
        if not validate_origin_header(origin, request.app.state.allowed_origins):
            logger.warning(f"CSRF: Invalid Origin header: {origin}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Invalid Origin header. CSRF protection triggered."}
            )
    else:
        # Fallback to Referer header validation
        referer = request.headers.get("Referer")
        if referer:
            if not validate_referer_header(referer, request.app.state.allowed_hosts):
                logger.warning(f"CSRF: Invalid Referer header: {referer}")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Invalid Referer header. CSRF protection triggered."}
                )
        else:
            # No Origin or Referer header - reject for security
            logger.warning("CSRF: Missing Origin and Referer headers for state-changing request")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Missing Origin/Referer header. CSRF protection requires these headers for state-changing requests."}
            )
    
    return await call_next(request)


# Audit Logging Middleware
async def audit_logging_middleware(request: Request, call_next):
    """
    Audit logging middleware for security and compliance.
    
    Logs all API requests with user, endpoint, status, and timing information.
    """
    # Skip audit logging for health check and static files
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    # Record start time
    start_time = time.time()
    
    # Get user identifier
    api_key = request.headers.get("X-API-Key", "")
    if api_key and api_key != "dev":
        user_id = _short_id(hash_api_key_for_logging(api_key))
    else:
        user_id = client_ip(request)
    
    # Get client IP
    ip_address = client_ip(request)
    
    # Process request
    response = None
    error = None
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        error = str(e)
        raise
    finally:
        # Calculate response time
        response_time = time.time() - start_time
        
        # Get status code
        status_code = response.status_code if response else 500
        
        # Log to audit system
        try:
            get_audit_logger().log_api_request(
                user_id=user_id,
                endpoint=request.url.path,
                method=request.method,
                status_code=status_code,
                response_time=response_time,
                ip_address=ip_address,
                error=error
            )
        except Exception as audit_error:
            logger.error(f"Audit logging failed: {audit_error}")


# Redis Rate Limiting Middleware
async def redis_rate_limit_middleware(request: Request, call_next):
    """
    Redis-based distributed rate limiting middleware.
    
    Implements Token Bucket algorithm with per-user, per-endpoint limits.
    Falls back to in-memory rate limiting if Redis unavailable.
    """
    # Skip rate limiting for health check and root endpoints
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    # Redis not available - use in-memory rate limiting (legacy behavior)
    if not runtime.redis_rate_limiter:
        return await call_next(request)

    user_id = _rate_limit_user_id(request)
    endpoint = request.url.path
    limit, window = get_rate_limit_for_endpoint(endpoint)

    allowed, info = runtime.redis_rate_limiter.check_rate_limit(
        user_id=user_id,
        endpoint=endpoint,
        limit=limit,
        window=window
    )

    if not allowed:
        # Rate limit exceeded - return 429
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": f"Rate limit exceeded. Maximum {limit} requests per {window} seconds.",
                "retry_after": info["retry_after"],
                "reset_at": info["reset_at"]
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(info["reset_at"]),
                "Retry-After": str(info["retry_after"])
            }
        )

    # Rate limit OK - add headers and continue
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    response.headers["X-RateLimit-Reset"] = str(info["reset_at"])

    return response


# Request logging middleware
async def log_requests(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    # Process request
    try:
        response = await call_next(request)
        
        # Log response
        duration = time.time() - start_time
        logger.info(
            f"Response: {request.method} {request.url.path} "
            f"Status: {response.status_code} Duration: {duration:.3f}s"
        )
        
        # Add timing header
        response.headers["X-Process-Time"] = str(duration)
        
        return response
        
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url.path} Error: {e}")
        raise


def install_middleware(app: FastAPI) -> None:
    """Register the middleware stack and remember the CSRF allow-lists on ``app.state``."""
    allowed_hosts = allowed_hosts_from_env()
    allowed_origins = cors_origins_from_env()
    app.state.allowed_hosts = allowed_hosts
    app.state.allowed_origins = allowed_origins

    # Middleware stack. Starlette makes the LAST registered middleware the
    # OUTERMOST one, so registration runs from innermost to outermost. Resulting
    # request flow (outer -> inner):
    #   CORS -> security headers -> request log -> audit -> rate limit -> CSRF origin
    #   check -> trusted host -> app
    # This way 429 (rate limit) and 403 (CSRF) rejections are still audited and
    # still carry security and CORS headers.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.middleware("http")(csrf_origin_referer_middleware)
    app.middleware("http")(redis_rate_limit_middleware)
    app.middleware("http")(audit_logging_middleware)
    app.middleware("http")(log_requests)
    app.middleware("http")(add_security_headers)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-CSRF-Token", "X-Requested-With"],  # Whitelist instead of wildcard
    )
