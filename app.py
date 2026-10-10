"""FastAPI application for CrawlLama - Production-ready API."""
import asyncio
import json
import logging
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime

import dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api import runtime
from api.constants import MAX_MEMORY_ENTRIES, MAX_QUERY_LENGTH
from api.dependencies import (
    check_rate_limit,
    verify_api_key,
    verify_csrf_token,
    verify_role,
)
from api.models import (
    AdaptiveQueryRequest,
    AdaptiveQueryResponse,
    CompanyOSINTRequest,
    ConfigUpdateRequest,
    ForgetRequest,
    HealthResponse,
    MemoryRequest,
    OSINTRequest,
    QueryRequest,
    QueryResponse,
    StatsResponse,
)
from api.routers.admin import router as admin_router
from api.security_config import (
    API_KEY,
    RATE_LIMIT,
    RATE_LIMIT_SECRET_EPHEMERAL,
    _dev_bypass_allowed,
    _is_loopback_host,
    _rate_limit_user_id,
    _short_id,
    hash_api_key_for_logging,
    is_dev_mode,
)
from api.validation import (
    filter_sensitive_config,
    validate_memory_category,
    validate_plugin_name,
)
from core.agent import SearchAgent
from core.agent.constants import QUICK_RESULT_REFERENCE_PATTERN
from core.api_key_manager import get_api_key_manager
from core.audit_logger import get_audit_logger
from core.csrf_manager import get_csrf_manager, validate_origin_header, validate_referer_header
from core.health import get_performance_tracker, get_system_monitor, print_health_summary, shutdown_monitoring
from core.langgraph_agent import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MAX_HOPS,
    MultiHopReasoningAgent,
    create_multihop_agent,
)
from core.memory_store import MemoryStore
from core.rbac_manager import Role, get_rbac_manager, get_role_hierarchy
from core.unified_loader import get_unified_loader
from utils.redis_rate_limiter import RedisRateLimiter, get_rate_limit_for_endpoint
from utils.tor_mode import TorError, initialize_tor_mode
from utils.validators import sanitize_exception_message

# Load environment variables
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("crawllama")

# Version constant (single source of truth in _version.py)
from _version import __version__ as VERSION  # noqa: E402 - needs logger configured first

# Initialize CSRF Manager
csrf_manager = get_csrf_manager()
logger.info("CSRF protection initialized")

# Initialize RBAC Manager
rbac_manager = get_rbac_manager()
logger.info("RBAC (Role-Based Access Control) initialized")

# Initialize Audit Logger
audit_logger = get_audit_logger()
logger.info("Audit logging initialized")

# Initialize API Key Manager (for rotation support)
api_key_manager = get_api_key_manager()
logger.info("API key rotation manager initialized")

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run startup/shutdown logic (modern replacement for on_event hooks)."""
    await startup_event()
    yield
    await shutdown_event()


app = FastAPI(
    title="CrawlLama API",
    description="AI-powered web research agent with multi-hop reasoning",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Mount static files for web interface
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("Static files mounted successfully")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# Security: Trusted Host Middleware (prevent Host header attacks)
# Get allowed hosts from env or use secure defaults (no wildcard in production!).
# 0.0.0.0 is a bind address, never a valid Host header value, so it is not an
# allowed host here.
allowed_hosts = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
# Add testserver only for the in-process test client (Starlette TestClient uses
# Host: testserver). Never enabled outside an explicit test environment.
if os.getenv("CRAWLLAMA_TESTING", "false").lower() == "true" or "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules:
    allowed_hosts.append("testserver")
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)

# CORS configuration
# SECURITY: No wildcard default - must be explicitly configured in production
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
        cors_origins = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:8000"]
else:
    # Development default - restrictive
    cors_origins = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:8000"]
    logger.warning("No ALLOWED_ORIGINS set. Using development defaults. Set ALLOWED_ORIGINS for production!")

# Store globally for CSRF validation
ALLOWED_ORIGINS = cors_origins
ALLOWED_HOSTS_LIST = allowed_hosts

# Paths exempt from rate limiting and audit logging (public docs/health endpoints)
PUBLIC_PATHS = frozenset({"/health", "/", "/docs", "/redoc", "/openapi.json"})
# Paths exempt from CSRF Origin/Referer validation
CSRF_EXEMPT_PATHS = PUBLIC_PATHS | {"/csrf-token"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-CSRF-Token", "X-Requested-With"],  # Whitelist instead of wildcard
)

# Security Headers Middleware
@app.middleware("http")
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
@app.middleware("http")
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
        if not validate_origin_header(origin, ALLOWED_ORIGINS):
            logger.warning(f"CSRF: Invalid Origin header: {origin}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Invalid Origin header. CSRF protection triggered."}
            )
    else:
        # Fallback to Referer header validation
        referer = request.headers.get("Referer")
        if referer:
            if not validate_referer_header(referer, ALLOWED_HOSTS_LIST):
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
@app.middleware("http")
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
        user_id = request.client.host if request.client else "unknown"
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
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
            audit_logger.log_api_request(
                user_id=user_id,
                endpoint=request.url.path,
                method=request.method,
                status_code=status_code,
                response_time=response_time,
                ip_address=client_ip,
                error=error
            )
        except Exception as audit_error:
            logger.error(f"Audit logging failed: {audit_error}")


# Redis Rate Limiting Middleware
@app.middleware("http")
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


# Load configuration
try:
    with open("config.json") as f:
        config = json.load(f)
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    config = {
        "llm": {"model": "qwen2.5:3b"},
        "cache": {"enabled": True}
    }


def validate_security_configuration():
    """Validate security configuration on startup.
    
    Checks for insecure configurations and logs warnings/errors.
    Only validates, does not block startup (except in strict mode).
    """
    issues = []
    warnings = []
    
    # Check if in DEV_MODE
    dev_mode = is_dev_mode()
    if dev_mode:
        warnings.append("⚠️  DEV_MODE is enabled - Security checks are relaxed")
    
    # Check API key configuration
    if not os.getenv("CRAWLLAMA_API_KEY"):
        if not dev_mode:
            warnings.append("⚠️  No CRAWLLAMA_API_KEY set - Using temporary key (insecure for production)")
    else:
        api_key = os.getenv("CRAWLLAMA_API_KEY")
        if len(api_key) < 32:
            issues.append("❌ CRAWLLAMA_API_KEY is too short (min 32 characters recommended)")
    
    # Check ALLOWED_HOSTS configuration
    if not os.getenv("ALLOWED_HOSTS"):
        warnings.append("⚠️  No ALLOWED_HOSTS set - Using defaults (configure for production)")
    
    # Check ALLOWED_ORIGINS configuration
    if not os.getenv("ALLOWED_ORIGINS"):
        warnings.append("⚠️  No ALLOWED_ORIGINS set - Using defaults (configure for production)")
    
    # Check RATE_LIMIT_SECRET
    if not os.getenv("RATE_LIMIT_SECRET"):
        warnings.append("⚠️  No RATE_LIMIT_SECRET set - Using temporary secret")
    
    # Check Redis configuration
    if not os.getenv("REDIS_URL"):
        warnings.append("ℹ️  No REDIS_URL set - Using in-memory fallbacks (not distributed)")
    
    # Log results
    if issues:
        logger.error("=" * 60)
        logger.error("🚨 SECURITY CONFIGURATION ISSUES 🚨")
        for issue in issues:
            logger.error(issue)
        logger.error("=" * 60)
    
    if warnings:
        logger.warning("=" * 60)
        logger.warning("🔒 SECURITY CONFIGURATION WARNINGS")
        for warning in warnings:
            logger.warning(warning)
        logger.warning("=" * 60)
    
    if not issues and not warnings:
        logger.info("✅ Security configuration validation passed")
    
    # In production strict mode, block startup on issues
    strict_mode = os.getenv("SECURITY_STRICT_MODE", "false").lower() == "true"
    if strict_mode and issues:
        logger.critical("SECURITY_STRICT_MODE enabled - Blocking startup due to security issues")
        raise RuntimeError("Security configuration validation failed in strict mode")
    
    return len(issues) == 0


def _enforce_dev_mode_loopback_only(dev_mode: bool) -> None:
    """Refuse to start in DEV_MODE when bound to a non-loopback address.

    SECURITY (fail closed): DEV_MODE disables API-key auth, CSRF and RBAC on
    EVERY endpoint (including /admin/* and /config). That is only acceptable on
    loopback. If the configured bind host is network-reachable, a single
    env-var misconfiguration would expose the entire unauthenticated admin
    surface — so refuse to start instead.
    """
    if not dev_mode:
        return
    host = (
        os.getenv("CRAWLLAMA_HOST")
        or os.getenv("HOST")
        or os.getenv("UVICORN_HOST")
        or "127.0.0.1"
    )
    if _is_loopback_host(host):
        return
    logger.critical(
        "CRAWLLAMA_DEV_MODE is enabled but the server is configured to bind a "
        f"non-loopback host ({host}). DEV_MODE disables authentication, CSRF and "
        "RBAC and must never be network-reachable. Refusing to start — unset "
        "CRAWLLAMA_DEV_MODE for production or bind to 127.0.0.1."
    )
    raise RuntimeError("DEV_MODE must not be bound to a non-loopback host")


def _enforce_persistent_rate_limit_secret(dev_mode: bool) -> None:
    """Refuse to start outside DEV_MODE without a persistent RATE_LIMIT_SECRET.

    SECURITY (fail closed): an ephemeral RATE_LIMIT_SECRET invalidates every
    issued managed-key hash on restart and yields non-portable rate-limit
    identities. Refuse to start in production without a persistent secret.
    """
    if RATE_LIMIT_SECRET_EPHEMERAL and not dev_mode:
        logger.critical(
            "RATE_LIMIT_SECRET is not set. Refusing to start outside DEV_MODE. "
            "Set RATE_LIMIT_SECRET in the environment for a persistent secret."
        )
        raise RuntimeError("RATE_LIMIT_SECRET is required outside DEV_MODE")


def _grant_bootstrap_admin_role() -> None:
    """Grant the bootstrap key administrative privileges.

    With the secure default role now READ_ONLY, the operator's bootstrap key
    must be explicitly elevated so that admin endpoints remain reachable out
    of the box.
    """
    try:
        bootstrap_user_id = hash_api_key_for_logging(API_KEY)
        rbac_manager.assign_role(bootstrap_user_id, Role.ADMIN, user_info="bootstrap")
        logger.info("Bootstrap API key granted ADMIN role")
    except Exception as e:
        logger.error(f"Failed to assign bootstrap admin role: {e}", exc_info=True)


def _create_redis_rate_limiter() -> RedisRateLimiter | None:
    """Initialize the Redis rate limiter; return None to fall back to in-memory limiting."""
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        limiter = RedisRateLimiter(redis_url=redis_url)
        logger.info(f"Redis rate limiter initialized: {redis_url}")
        return limiter
    except Exception as e:
        logger.warning(f"Failed to initialize Redis rate limiter: {e}")
        logger.warning("Falling back to in-memory rate limiting")
        return None


def _create_health_monitoring() -> tuple:
    """Initialize health monitoring; return (system_monitor, performance_tracker) or (None, None)."""
    try:
        monitor = get_system_monitor()
        tracker = get_performance_tracker()
        logger.info("Health monitoring initialized")
        return monitor, tracker
    except Exception as e:
        logger.error(f"Failed to initialize health monitoring: {e}", exc_info=True)
        # Continue without health monitoring
        return None, None


def _create_memory_store() -> MemoryStore | None:
    """Initialize the memory store; return None on failure."""
    try:
        store = MemoryStore()
        logger.info("Memory store initialized")
        return store
    except Exception as e:
        logger.error(f"Failed to initialize memory store: {e}", exc_info=True)
        # Continue without memory store
        return None


def _create_standard_agent() -> SearchAgent | None:
    """Initialize the standard search agent; return None on failure."""
    try:
        search_agent = SearchAgent(config=config, enable_web=True, debug=False)
        logger.info("Standard agent initialized")
        return search_agent
    except Exception as e:
        logger.error(f"Failed to initialize standard agent: {e}", exc_info=True)
        # Continue without standard agent
        return None


def _create_multihop_agent() -> MultiHopReasoningAgent | None:
    """Initialize the multi-hop reasoning agent; return None on failure."""
    try:
        reasoning_agent = create_multihop_agent(config)
        logger.info("Multi-hop agent initialized")
        return reasoning_agent
    except Exception as e:
        logger.error(f"Failed to initialize multi-hop agent: {e}", exc_info=True)
        # Continue without multi-hop agent
        return None


def _create_adaptive_system(search_agent, reasoning_agent, monitor, tracker) -> tuple:
    """Initialize the Adaptive Hopping System; return (manager, processor) or (None, None)."""
    try:
        from core.adaptive_integration import initialize_adaptive_system
        from core.cloud_llm_client import create_llm_client_from_config

        # LLM client for complexity detection - provider-aware, so cloud
        # configs get working adaptive features too (previously Ollama-only).
        llm = create_llm_client_from_config(config.get("llm", {}))

        manager, processor = initialize_adaptive_system(
            llm=llm,
            agent=search_agent,
            multihop_agent=reasoning_agent,
            system_monitor=monitor,
            performance_tracker=tracker
        )
        logger.info("Adaptive Hopping System initialized")
        return manager, processor
    except Exception as e:
        logger.error(f"Failed to initialize Adaptive Hopping System: {e}", exc_info=True)
        logger.warning("API will continue without adaptive features")
        return None, None


async def startup_event():
    """Initialize components on startup."""

    logger.info("Starting CrawlLama API...")

    # Tor mode must be active (and verified) before any component can make a
    # web request; an unreachable Tor network aborts startup (fail fast).
    try:
        tor_config = initialize_tor_mode(config)
    except TorError as e:
        logger.critical(f"Startup aborted: {e}")
        raise
    if tor_config.enabled:
        logger.info(f"Tor mode active: all web traffic routed via {tor_config.proxy_url}")

    dev_mode = is_dev_mode()

    _enforce_dev_mode_loopback_only(dev_mode)
    _enforce_persistent_rate_limit_secret(dev_mode)

    # Validate security configuration FIRST
    try:
        validate_security_configuration()
    except RuntimeError as e:
        logger.critical(f"Startup aborted: {e}")
        raise

    if not dev_mode:
        _grant_bootstrap_admin_role()

    # Store startup time for uptime calculation
    app.state.start_time = time.time()

    # Initialize components (each falls back to None/degraded mode on failure)
    runtime.redis_rate_limiter = _create_redis_rate_limiter()
    runtime.system_monitor, performance_tracker = _create_health_monitoring()
    runtime.memory_store = _create_memory_store()
    runtime.agent = _create_standard_agent()
    runtime.multihop_agent = _create_multihop_agent()

    # Check if critical components are initialized
    if not runtime.agent and not runtime.multihop_agent:
        logger.warning("WARNING: No agents initialized! API will have limited functionality.")

    runtime.adaptive_manager, adaptive_query_processor = _create_adaptive_system(
        runtime.agent, runtime.multihop_agent, runtime.system_monitor, runtime.performance_tracker
    )

    logger.info("CrawlLama API started successfully")


async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down CrawlLama API...")

    # Close Redis connection
    if runtime.redis_rate_limiter:
        try:
            runtime.redis_rate_limiter.close()
            logger.info("Redis rate limiter closed")
        except Exception as e:
            logger.error(f"Error closing Redis rate limiter: {e}")

    # Print final health summary
    if runtime.system_monitor and runtime.performance_tracker:
        logger.info("Final health summary:")
        print_health_summary()

    # Shutdown monitoring
    shutdown_monitoring()

    logger.info("CrawlLama API shutdown complete")


# Request logging middleware
@app.middleware("http")
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


config_lock = threading.Lock()  # Thread-safe config file writes


# Mount extracted endpoint routers
app.include_router(admin_router)


# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - serves web interface."""
    def _read_index() -> str:
        with open("static/index.html", encoding="utf-8") as f:
            return f.read()

    try:
        # File I/O runs off the event loop
        return HTMLResponse(content=await asyncio.to_thread(_read_index))
    except FileNotFoundError:
        # Fallback to JSON if HTML not found
        return JSONResponse({
            "name": "CrawlLama API",
            "version": VERSION,
            "description": "AI-powered web research agent",
            "docs": "/docs",
            "health": "/health",
            "security": "API Key required (set X-API-Key header or CRAWLLAMA_DEV_MODE=true)"
        })

@app.get("/api", response_model=dict[str, str])
async def api_info():
    """API information endpoint."""
    return {
        "name": "CrawlLama API",
        "version": VERSION,
        "description": "AI-powered web research agent",
        "docs": "/docs",
        "health": "/health",
        "security": "API Key required (set X-API-Key header or CRAWLLAMA_DEV_MODE=true)"
    }


@app.get("/security-info", dependencies=[Depends(verify_api_key)])
async def security_info():
    """Get security configuration info (non-sensitive).

    Requires authentication to avoid handing the feature/role inventory to
    anonymous reconnaissance.
    """
    return {
        "rate_limit": f"{RATE_LIMIT} requests/minute",
        "max_query_length": MAX_QUERY_LENGTH,
        "max_memory_entries": MAX_MEMORY_ENTRIES,
        "authentication": "API Key (X-API-Key header)",
        "authorization": "Role-Based Access Control (RBAC)",
        "roles": get_role_hierarchy(),
        "dev_mode": os.getenv("CRAWLLAMA_DEV_MODE", "false"),
        "cors_origins": "Configured" if os.getenv("ALLOWED_ORIGINS") else "Development defaults (localhost only)",
        "features": {
            "rate_limiting": True,
            "csrf_protection": True,
            "rbac": True,
            "query_sanitization": True,
            "input_validation": True,
            "request_logging": True,
            "trusted_hosts": True,
            "origin_validation": True
        },
        "note": "API key required for all endpoints (except /health and /). Role determines access level."
    }


@app.post("/csrf-token")
async def get_csrf_token(api_key: str = Depends(verify_api_key)):
    """Generate a CSRF token for the authenticated user.
    
    CSRF tokens are required for all state-changing operations (POST/PUT/PATCH/DELETE).
    Include the token in the X-CSRF-Token header for protected requests.
    
    Tokens expire after 1 hour by default.
    """
    # Use hashed API key as user ID
    user_id = hash_api_key_for_logging(api_key)
    
    # Generate token
    token = csrf_manager.generate_token(user_id)
    
    return {
        "csrf_token": token,
        "expires_in": csrf_manager.token_expiry,
        "usage": "Include this token in X-CSRF-Token header for POST/PUT/PATCH/DELETE requests",
        "note": "Token is bound to your API key and expires after the specified time"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    components = {
        "agent": "healthy" if runtime.agent else "unavailable",
        "multihop_agent": "healthy" if runtime.multihop_agent else "unavailable",
        "memory_store": "healthy" if runtime.memory_store else "unavailable",
        "system_monitor": "healthy" if runtime.system_monitor else "unavailable",
        "performance_tracker": "healthy" if runtime.performance_tracker else "unavailable"
    }

    return HealthResponse(
        status="healthy" if all(v == "healthy" for v in components.values()) else "degraded",
        timestamp=datetime.now().isoformat(),
        version=VERSION,
        components=components
    )


async def _run_multihop_query(request: QueryRequest, start_time: float) -> QueryResponse:
    """Answer a query with the multi-hop reasoning agent."""
    if not runtime.multihop_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Multi-hop agent not available"
        )

    # Use custom max_hops if provided (pydantic guarantees 1 <= max_hops <= 5)
    if request.max_hops and request.max_hops != DEFAULT_MAX_HOPS:
        reasoning_agent = MultiHopReasoningAgent(
            config=config,
            max_hops=request.max_hops,
            confidence_threshold=DEFAULT_CONFIDENCE_THRESHOLD
        )
    else:
        reasoning_agent = runtime.multihop_agent

    # Offload the blocking (sync HTTP + LLM) work to a worker thread
    # so it does not stall the event loop and kill concurrency.
    result = await asyncio.to_thread(reasoning_agent.query, request.query)

    return QueryResponse(
        answer=result["answer"],
        confidence=result.get("confidence"),
        steps=result.get("steps"),
        search_queries=result.get("search_queries"),
        reasoning_path=result.get("reasoning_path"),
        elapsed_time=time.time() - start_time,
        cached=False
    )


async def _run_standard_query(request: QueryRequest, start_time: float) -> QueryResponse:
    """Answer a query with the standard search agent."""
    if not runtime.agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not available"
        )

    answer = await asyncio.to_thread(
        runtime.agent.query, request.query, use_tools=request.use_tools
    )

    return QueryResponse(
        answer=answer,
        elapsed_time=time.time() - start_time,
        cached=False
    )


@app.post("/query", response_model=QueryResponse, dependencies=[Depends(check_rate_limit)])
async def query_endpoint(request: QueryRequest):
    """
    Main query endpoint for processing search queries.

    Args:
        request: Query request with parameters

    Returns:
        Query response with answer and metadata
    """
    start_time = time.time()

    try:
        logger.info("Processing query: '%s' (multihop=%s)", request.query, request.use_multihop)  # lgtm[py/log-injection] - parameterized logging; false positive

        # BUGFIX: Check if query is a result reference or uses < prefix
        # These should ALWAYS use SearchAgent, never MultiHopReasoningAgent
        query_lower = request.query.lower().strip()
        is_context_mode = request.query.strip().startswith('<')
        is_result_ref = bool(QUICK_RESULT_REFERENCE_PATTERN.search(query_lower))

        # Force SearchAgent for result references and context-only mode
        use_multihop = request.use_multihop and not is_context_mode and not is_result_ref

        if is_context_mode or is_result_ref:
            logger.info(f"Forcing SearchAgent (context_mode={is_context_mode}, result_ref={is_result_ref})")

        if use_multihop:
            return await _run_multihop_query(request, start_time)
        return await _run_standard_query(request, start_time)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query processing failed. Please check your input and try again."
        ) from e


@app.post("/query-adaptive", response_model=AdaptiveQueryResponse, dependencies=[Depends(check_rate_limit)])
async def adaptive_query_endpoint(request: AdaptiveQueryRequest):
    """
    Adaptive query endpoint with intelligent agent selection.

    Uses the Adaptive Hopping System to automatically select the best agent
    (SearchAgent or MultiHopReasoningAgent) based on query complexity.

    Features:
    - Automatic complexity detection (LOW/MID/HIGH)
    - Confidence-based escalation
    - Resource-aware degradation
    - Force complexity override
    - Detailed strategy metadata

    Args:
        request: Adaptive query request with parameters

    Returns:
        Adaptive query response with answer, strategy, and metadata
    """
    try:
        logger.info(
            "Processing adaptive query: '%s' (force_complexity=%s, enable_escalation=%s)",
            request.query,
            request.force_complexity,
            request.enable_escalation
        )  # lgtm[py/log-injection] - parameterized logging; false positive

        if not runtime.adaptive_query_processor:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Adaptive Hopping System not available. Please check system configuration."
            )

        # Process query with adaptive system (offloaded; it performs blocking
        # sync HTTP + LLM work that must not stall the event loop).
        result = await asyncio.to_thread(
            runtime.adaptive_query_processor.process_query,
            query=request.query,
            force_complexity=request.force_complexity,
            enable_escalation=request.enable_escalation,
        )

        logger.info(
            f"Adaptive query completed | "
            f"Complexity: {result['strategy']['complexity']} | "
            f"Agent: {result['strategy']['agent_type']} | "
            f"Attempts: {result['metadata']['attempts']} | "
            f"Time: {result['metadata']['elapsed_time']:.2f}s"
        )

        return AdaptiveQueryResponse(
            answer=result["answer"],
            confidence=result.get("confidence"),
            strategy=result["strategy"],
            metadata=result["metadata"],
            steps=result.get("steps"),
            search_queries=result.get("search_queries"),
            reasoning_path=result.get("reasoning_path")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Adaptive query processing failed: {sanitize_exception_message(str(e))}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Adaptive query processing failed"
        ) from e


@app.get("/stats", response_model=StatsResponse, dependencies=[Depends(check_rate_limit)])
async def stats_endpoint():
    """Get system statistics."""
    try:
        agent_stats = runtime.agent.get_stats() if runtime.agent else {}

        # Gather resource stats from health monitoring
        resource_stats = {}
        if runtime.system_monitor:
            metrics = runtime.system_monitor.get_latest_metrics()
            if metrics:
                resource_stats["system"] = {
                    "cpu_percent": metrics.cpu_percent,
                    "memory_percent": metrics.memory_percent,
                    "memory_used_gb": metrics.memory_used_gb,
                    "memory_total_gb": metrics.memory_total_gb,
                    "disk_percent": metrics.disk_percent,
                }

        if runtime.performance_tracker:
            perf_stats = runtime.performance_tracker.get_all_stats()
            resource_stats["performance"] = {
                op: {
                    "count": stats.count,
                    "avg_duration_ms": stats.avg_duration_ms,
                    "p95_duration_ms": stats.p95_duration_ms,
                    "success_rate": stats.success_rate
                }
                for op, stats in perf_stats.items()
            }

        return StatsResponse(
            agent_stats=agent_stats,
            resource_stats=resource_stats,
            uptime=time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0
        )

    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        ) from e


@app.get("/plugins", dependencies=[Depends(check_rate_limit)])
async def list_plugins():
    """List available plugins."""
    try:
        loader = get_unified_loader()
        available = loader.discover_plugins()
        loaded = loader.get_loaded_plugins()

        return {
            "available": available,
            "loaded": loaded,
            "count": {
                "available": len(available),
                "loaded": len(loaded)
            }
        }

    except Exception as e:
        logger.error(f"Failed to list plugins: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list plugins"
        ) from e


@app.post("/plugins/{plugin_name}/load", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
async def load_plugin(plugin_name: str):
    """Load a plugin dynamically. (Admin only)"""
    try:
        # Validate plugin name to prevent path traversal
        plugin_name = validate_plugin_name(plugin_name)

        loader = get_unified_loader()
        loader.load_plugin(plugin_name)

        return {
            "status": "loaded",
            "plugin": plugin_name,
            "message": f"Plugin '{plugin_name}' loaded successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to load plugin '%s': %s", plugin_name, e, exc_info=True)  # lgtm[py/log-injection] - parameterized logging; false positive
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to load plugin. Please check if the plugin exists and is valid."
        ) from e


@app.post("/plugins/{plugin_name}/unload", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
async def unload_plugin(plugin_name: str):
    """Unload a plugin. (Admin only)"""
    try:
        # Validate plugin name to prevent path traversal
        plugin_name = validate_plugin_name(plugin_name)

        loader = get_unified_loader()
        loader.unload_plugin(plugin_name)

        return {
            "status": "unloaded",
            "plugin": plugin_name,
            "message": f"Plugin '{plugin_name}' unloaded successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to unload plugin '%s': %s", plugin_name, e, exc_info=True)  # lgtm[py/log-injection] - parameterized logging; false positive
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to unload plugin. Please check if the plugin is loaded."
        ) from e


@app.get("/tools", dependencies=[Depends(check_rate_limit)])
async def list_tools():
    """List loaded tools."""
    try:
        loader = get_unified_loader()

        loaded_tools = loader.get_loaded_tools()
        return {
            "loaded": loaded_tools,
            "count": len(loaded_tools)
        }

    except Exception as e:
        logger.error(f"Failed to list tools: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tools"
        ) from e


@app.post("/cache/clear", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def clear_cache():
    """Clear application cache."""
    try:
        if runtime.agent and runtime.agent.cache:
            count = runtime.agent.cache.clear()
            return {"status": "success", "message": f"Cache cleared ({count} entries)"}
        else:
            return {"status": "info", "message": "No cache to clear"}

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        ) from e


@app.get("/cache/stats", dependencies=[Depends(check_rate_limit)])
async def cache_stats():
    """Get cache statistics."""
    try:
        if runtime.agent and runtime.agent.cache:
            stats = runtime.agent.cache.get_stats()
            return {
                "status": "success",
                "data": stats
            }
        else:
            return {
                "status": "info",
                "message": "No cache available",
                "data": {}
            }

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cache stats"
        ) from e


@app.post("/session/clear", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def clear_session():
    """Clear conversation session."""
    try:
        if runtime.agent:
            result = runtime.agent.clear_session()
            return {
                "status": "success",
                "message": "Session cleared",
                "data": result
            }
        else:
            return {"status": "info", "message": "No session to clear"}

    except Exception as e:
        logger.error(f"Failed to clear session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear session"
        ) from e


@app.post("/session/save", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def save_session():
    """Save current session."""
    try:
        if runtime.agent:
            runtime.agent.save_session()
            return {
                "status": "success",
                "message": "Session saved"
            }
        else:
            return {"status": "info", "message": "No session to save"}

    except Exception as e:
        logger.error(f"Failed to save session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save session"
        ) from e


@app.post("/session/load", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def load_session():
    """Load saved session."""
    try:
        if runtime.agent:
            runtime.agent.load_session()
            return {
                "status": "success",
                "message": "Session loaded"
            }
        else:
            return {"status": "info", "message": "No agent to load session into"}

    except Exception as e:
        logger.error(f"Failed to load session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load session"
        ) from e


@app.get("/config", dependencies=[Depends(check_rate_limit)])
async def get_config():
    """Get current configuration (sensitive values redacted)."""
    try:
        # Thread-safe config read
        with config_lock:
            # Filter sensitive data before returning
            filtered_config = filter_sensitive_config(config)

        return {
            "status": "success",
            "data": filtered_config,
            "note": "Sensitive values are redacted for security"
        }

    except Exception as e:
        logger.error(f"Failed to get config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get config"
        ) from e


@app.patch("/config", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
async def update_config(request: ConfigUpdateRequest):
    """Update configuration setting. (Admin only)"""
    try:
        if request.category not in config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category: {request.category}"
            )

        if request.key not in config[request.category]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid key: {request.key} in category {request.category}"
            )

        # Thread-safe config update; the write is atomic (tmp + rename) so a
        # crash cannot truncate config.json, and runs off the event loop.
        def _update_and_write_config():
            with config_lock:
                config[request.category][request.key] = request.value
                tmp_path = "config.json.tmp"
                with open(tmp_path, "w") as f:
                    json.dump(config, f, indent=2)
                os.replace(tmp_path, "config.json")

        await asyncio.to_thread(_update_and_write_config)

        return {
            "status": "success",
            "message": f"Updated {request.category}.{request.key}",
            "category": request.category,
            "key": request.key,
            "value": request.value,
            "note": "Restart API for changes to take effect"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update configuration. Please check your input."
        ) from e


@app.get("/context/status", dependencies=[Depends(check_rate_limit)])
async def context_status():
    """Get context usage status."""
    try:
        if runtime.agent and hasattr(runtime.agent, 'context_manager'):
            context_mgr = runtime.agent.context_manager
            return {
                "status": "success",
                "data": {
                    "max_tokens": context_mgr.max_tokens,
                    "model": context_mgr.model_name,
                    "encoding": context_mgr.encoding.name if hasattr(context_mgr, 'encoding') else "unknown"
                }
            }
        else:
            return {
                "status": "info",
                "message": "Context manager not available",
                "data": {}
            }

    except Exception as e:
        logger.error(f"Failed to get context status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get context status"
        ) from e


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    # SECURITY: Do not leak the exception class name to clients; it aids
    # fingerprinting of internals. The full detail is in the server logs.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


# Memory Store Endpoints
@app.get("/memory", dependencies=[Depends(check_rate_limit)])
async def get_memory():
    """Get all memory store entries."""
    try:
        if not runtime.memory_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory store not available"
            )

        return {
            "status": "success",
            "data": runtime.memory_store.get_all()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get memory: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memory data"
        ) from e


@app.post("/memory/remember", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def remember(request: MemoryRequest):
    """Remember a value in memory store."""
    try:
        if not runtime.memory_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory store not available"
            )

        # Validate category
        validate_memory_category(request.category)

        # Call the appropriate remember method based on category
        category_methods = {
            'email': runtime.memory_store.remember_email,
            'emails': runtime.memory_store.remember_email,
            'phone': runtime.memory_store.remember_phone,
            'phones': runtime.memory_store.remember_phone,
            'ip': runtime.memory_store.remember_ip,
            'ips': runtime.memory_store.remember_ip,
            'username': runtime.memory_store.remember_username,
            'usernames': runtime.memory_store.remember_username,
            'domain': runtime.memory_store.remember_domain,
            'domains': runtime.memory_store.remember_domain,
        }

        method = category_methods.get(request.category.lower())
        if not method:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported category: {request.category}"
            )

        success = method(request.value)

        return {
            "status": "success" if success else "failed",
            "category": request.category,
            "value": request.value,
            "message": f"Remembered {request.category}: {request.value}" if success else "Failed to remember"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remember: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store memory"
        ) from e


@app.get("/memory/recall/{category}", dependencies=[Depends(check_rate_limit)])
async def recall(category: str):
    """Recall values from memory store by category."""
    try:
        if not runtime.memory_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory store not available"
            )

        # Validate category
        validate_memory_category(category)

        # Call the appropriate get method based on category
        category_methods = {
            'email': runtime.memory_store.get_all_emails,
            'emails': runtime.memory_store.get_all_emails,
            'phone': runtime.memory_store.get_all_phones,
            'phones': runtime.memory_store.get_all_phones,
            'ip': runtime.memory_store.get_all_ips,
            'ips': runtime.memory_store.get_all_ips,
            'username': runtime.memory_store.get_all_usernames,
            'usernames': runtime.memory_store.get_all_usernames,
            'domain': runtime.memory_store.get_all_domains,
            'domains': runtime.memory_store.get_all_domains,
            'note': runtime.memory_store.get_all_notes,
            'notes': runtime.memory_store.get_all_notes,
        }

        method = category_methods.get(category.lower())
        if not method:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported category: {category}"
            )

        results = method()

        return {
            "status": "success",
            "category": category,
            "count": len(results),
            "results": results
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to recall: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memory"
        ) from e


@app.get("/memory/stats", dependencies=[Depends(check_rate_limit)])
async def memory_stats():
    """Get memory store statistics."""
    try:
        if not runtime.memory_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory store not available"
            )

        summary = runtime.memory_store.get_summary()

        return {
            "status": "success",
            "summary": summary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get memory statistics"
        ) from e


@app.delete("/memory/forget", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def forget(request: ForgetRequest):
    """Forget values from memory store."""
    try:
        if not runtime.memory_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory store not available"
            )

        if request.category == "all" or (not request.category and not request.value):
            # Clear all memory
            success = runtime.memory_store.clear_all()
            return {
                "status": "success" if success else "failed",
                "message": "All memory cleared" if success else "Failed to clear memory"
            }

        # Validate category if provided and not "all"
        if request.category:
            validate_memory_category(request.category)

        if request.value:
            # Forget specific value using category-specific methods
            forget_methods = {
                'email': runtime.memory_store.forget_email,
                'emails': runtime.memory_store.forget_email,
                'phone': runtime.memory_store.forget_phone,
                'phones': runtime.memory_store.forget_phone,
                'ip': runtime.memory_store.forget_ip,
                'ips': runtime.memory_store.forget_ip,
                'username': runtime.memory_store.forget_username,
                'usernames': runtime.memory_store.forget_username,
                'domain': runtime.memory_store.forget_domain,
                'domains': runtime.memory_store.forget_domain,
                'note': runtime.memory_store.forget_note,
                'notes': runtime.memory_store.forget_note,
            }

            method = forget_methods.get(request.category.lower())
            if not method:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported category for forget: {request.category}"
                )

            success = method(request.value)
            return {
                "status": "success" if success else "failed",
                "category": request.category,
                "value": request.value,
                "message": f"Deleted {request.category}: {request.value}" if success else "Value not found"
            }

        if request.category:
            # Forget entire category
            success = runtime.memory_store.clear_category(request.category)
            return {
                "status": "success" if success else "failed",
                "category": request.category,
                "message": f"Cleared {request.category} category" if success else "Failed to clear category"
            }

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide category, value, or 'all'"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to forget: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete memory data"
        ) from e


# OSINT Endpoints
@app.post("/osint/query", dependencies=[Depends(check_rate_limit)])
async def osint_query(request: OSINTRequest):
    """Execute OSINT query with operators."""
    try:
        if not runtime.agent:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Agent not available"
            )

        start_time = time.time()
        answer = await asyncio.to_thread(runtime.agent.query, request.query, use_tools=True)

        return {
            "status": "success",
            "query": request.query,
            "answer": answer,
            "elapsed_time": time.time() - start_time
        }

    except HTTPException:
        raise
    except Exception as e:
        # Sanitize exception message and log stack trace only at debug level
        sanitized_error = sanitize_exception_message(str(e))
        logger.error(f"OSINT query failed: {sanitized_error}")  # lgtm[py/stack-trace-exposure] - Error message is sanitized and stack trace is not exposed to users
        logger.debug("Full OSINT query exception details (suppressed)")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OSINT query failed. Please check your input and try again."
        ) from e


@app.post("/osint/company", dependencies=[Depends(check_rate_limit)])
async def osint_company(request: CompanyOSINTRequest):
    """Execute company-focused OSINT query using natural input."""
    try:
        if not runtime.agent:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Agent not available"
            )

        start_time = time.time()
        query_parts = [f"analyze company {request.company_name}"]

        if request.country:
            query_parts.append(f"country:{request.country}")
        if request.region:
            query_parts.append(f"region:{request.region}")
        if request.language:
            query_parts.append(f"lang:{request.language}")

        synthesized_query = " ".join(query_parts)
        answer = await asyncio.to_thread(runtime.agent.query, synthesized_query, use_tools=True)

        return {
            "status": "success",
            "company_name": request.company_name,
            "query": synthesized_query,
            "answer": answer,
            "elapsed_time": time.time() - start_time
        }

    except HTTPException:
        raise
    except Exception as e:
        sanitized_error = sanitize_exception_message(str(e))
        logger.error(f"Company OSINT query failed: {sanitized_error}")
        logger.debug("Full company OSINT exception details (suppressed)")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Company OSINT query failed. Please check your input and try again."
        ) from e


# Development Endpoint: Retrieve temporary API key
@app.get("/dev/api-key")
async def get_dev_api_key(request: Request):
    """
    Retrieve the temporary API key (only available in DEV_MODE).

    Security: This endpoint is ONLY accessible when CRAWLLAMA_DEV_MODE=true
    AND the request originates from the loopback interface.
    Never expose this in production!
    """
    if not is_dev_mode():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Endpoint not available in production mode",
                "message": "This development endpoint is disabled for security reasons.",
                "solution": "To access the API key in development mode, set environment variable: CRAWLLAMA_DEV_MODE=true"
            }
        )

    # Defense in depth: never serve the key to a non-loopback client, even in
    # DEV_MODE, so an accidentally exposed dev server cannot leak the key.
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "testclient"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not available"
        )

    # Only return if API_KEY was auto-generated (not from .env)
    if not os.getenv("CRAWLLAMA_API_KEY"):
        return {
            "status": "success",
            "api_key": API_KEY,
            "warning": "This is a temporary key for development only. Set CRAWLLAMA_API_KEY in .env for production.",
            "usage": f"Add this header to your requests: X-API-Key: {API_KEY}"
        }
    else:
        return {
            "status": "info",
            "message": "API key is configured via environment variable. Check your .env file."
        }


if __name__ == "__main__":
    import uvicorn

    # Bind host is loopback by default; if overridden via env, the DEV_MODE
    # loopback guard (_enforce_dev_mode_loopback_only) refuses to start when
    # DEV_MODE is also enabled on a network-reachable host.
    uvicorn.run(
        "app:app",
        host=os.getenv("CRAWLLAMA_HOST") or os.getenv("HOST") or "127.0.0.1",
        port=int(os.getenv("CRAWLLAMA_PORT") or os.getenv("PORT") or "8000"),
        reload=False,
        log_level="info"
    )
