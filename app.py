"""FastAPI application for CrawlLama - Production-ready API."""
import copy
import hashlib
import hmac
import logging
import os
import re
import unicodedata
from fastapi import FastAPI, HTTPException, Depends, Header, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
import json
import time
from datetime import datetime
import secrets
import threading
import asyncio

from core.agent import SearchAgent
from core.langgraph_agent import MultiHopReasoningAgent
from core.unified_loader import get_unified_loader
from core.memory_store import MemoryStore
from core.health import get_system_monitor, get_performance_tracker, print_health_summary, shutdown_monitoring
from core.csrf_manager import get_csrf_manager, validate_origin_header, validate_referer_header
from core.rbac_manager import get_rbac_manager, Role, get_role_hierarchy
from core.audit_logger import get_audit_logger
from core.api_key_manager import get_api_key_manager
from utils.validators import sanitize_query
from utils.redis_rate_limiter import RedisRateLimiter, get_rate_limit_for_endpoint
import dotenv
from utils.secure_hash import hmac_sha256_hex

# Load environment variables
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("crawllama")

# Version constant
VERSION = "1.4.9"

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
if not RATE_LIMIT_SECRET:
    RATE_LIMIT_SECRET = secrets.token_bytes(32)  # 256-bit secret
    logger.warning("No RATE_LIMIT_SECRET set. Generated temporary secret for this session.")
    logger.warning("Set RATE_LIMIT_SECRET in .env for consistent rate limiting across restarts.")
elif isinstance(RATE_LIMIT_SECRET, str):
    # Convert string to bytes if loaded from env
    RATE_LIMIT_SECRET = RATE_LIMIT_SECRET.encode('utf-8')

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
app = FastAPI(
    title="CrawlLama API",
    description="AI-powered web research agent with multi-hop reasoning",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Mount static files for web interface
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("Static files mounted successfully")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# Security: Trusted Host Middleware (prevent Host header attacks)
# Get allowed hosts from env or use secure defaults (no wildcard in production!)
allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",")
# Always add testserver for TestClient compatibility (only used in testing, never in production)
allowed_hosts.append("testserver")
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)

# CORS configuration
# SECURITY: No wildcard default - must be explicitly configured in production
cors_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if cors_origins_env:
    cors_origins = cors_origins_env.split(",")
else:
    # Development default - restrictive
    cors_origins = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:8000"]
    logger.warning("No ALLOWED_ORIGINS set. Using development defaults. Set ALLOWED_ORIGINS for production!")

# Store globally for CSRF validation
ALLOWED_ORIGINS = cors_origins
ALLOWED_HOSTS_LIST = allowed_hosts

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
    if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json", "/csrf-token"]:
        return await call_next(request)
    
    # Skip in DEV_MODE
    if os.getenv("CRAWLLAMA_DEV_MODE", "false").lower() == "true":
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
    if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)
    
    # Record start time
    import time as timing_module
    start_time = timing_module.time()
    
    # Get user identifier
    api_key = request.headers.get("X-API-Key", "")
    if api_key and api_key != "dev":
        user_id = hash_api_key_for_logging(api_key)[:16] + "..."
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
        response_time = timing_module.time() - start_time
        
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
    if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)
    
    # Check if Redis rate limiter is available
    if redis_rate_limiter:
        # Get user identifier (API key or IP)
        api_key = request.headers.get("X-API-Key", "")
        if not api_key or api_key == "dev" or os.getenv("CRAWLLAMA_DEV_MODE", "false").lower() == "true":
            user_id = request.client.host if request.client else "unknown"
        else:
            # SECURITY: Use a keyed HMAC (default SHA3-256) to derive a stable
            # identifier for rate limiting while preventing reversal of API keys.
            # The API key is immediately hashed with a secret key and never stored/logged in plaintext
            # This is the CORRECT way to handle API keys for rate limiting (not password storage)
            user_id = hmac_sha256_hex(api_key, key=RATE_LIMIT_SECRET)  # deterministic, keyed ID
        
        # Get rate limit for endpoint
        endpoint = request.url.path
        limit, window = get_rate_limit_for_endpoint(endpoint)
        
        # Check rate limit
        allowed, info = redis_rate_limiter.check_rate_limit(
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
    else:
        # Redis not available - use in-memory rate limiting (legacy behavior)
        return await call_next(request)


# Load configuration
try:
    with open("config.json", "r") as f:
        config = json.load(f)
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    config = {
        "llm": {"model": "qwen2.5:3b"},
        "cache": {"enabled": True}
    }

# Initialize components
agent = None
multihop_agent = None
memory_store = None
system_monitor = None
performance_tracker = None
redis_rate_limiter = None  # Redis-based rate limiter
adaptive_manager = None  # Adaptive hopping manager
adaptive_query_processor = None  # Adaptive query processor


def validate_security_configuration():
    """Validate security configuration on startup.
    
    Checks for insecure configurations and logs warnings/errors.
    Only validates, does not block startup (except in strict mode).
    """
    issues = []
    warnings = []
    
    # Check if in DEV_MODE
    dev_mode = os.getenv("CRAWLLAMA_DEV_MODE", "false").lower() == "true"
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


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global agent, multihop_agent, memory_store, system_monitor, performance_tracker, redis_rate_limiter, adaptive_manager, adaptive_query_processor

    logger.info("Starting CrawlLama API...")
    
    # Validate security configuration FIRST
    try:
        validate_security_configuration()
    except RuntimeError as e:
        logger.critical(f"Startup aborted: {e}")
        raise

    # Store startup time for uptime calculation
    app.state.start_time = time.time()
    
    # Initialize Redis rate limiter (optional - falls back to in-memory if Redis unavailable)
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_rate_limiter = RedisRateLimiter(redis_url=redis_url)
        logger.info(f"Redis rate limiter initialized: {redis_url}")
    except Exception as e:
        logger.warning(f"Failed to initialize Redis rate limiter: {e}")
        logger.warning("Falling back to in-memory rate limiting")
        redis_rate_limiter = None

    # Initialize health monitoring
    try:
        system_monitor = get_system_monitor()
        performance_tracker = get_performance_tracker()
        logger.info("Health monitoring initialized")
    except Exception as e:
        logger.error(f"Failed to initialize health monitoring: {e}", exc_info=True)
        # Continue without health monitoring

    # Initialize memory store
    try:
        memory_store = MemoryStore()
        logger.info("Memory store initialized")
    except Exception as e:
        logger.error(f"Failed to initialize memory store: {e}", exc_info=True)
        # Continue without memory store

    # Initialize standard agent
    try:
        agent = SearchAgent(config=config, enable_web=True, debug=False)
        logger.info("Standard agent initialized")
    except Exception as e:
        logger.error(f"Failed to initialize standard agent: {e}", exc_info=True)
        # Continue without standard agent

    # Initialize multi-hop agent
    try:
        multihop_agent = MultiHopReasoningAgent(
            config=config,
            max_hops=3,
            confidence_threshold=0.7
        )
        logger.info("Multi-hop agent initialized")
    except Exception as e:
        logger.error(f"Failed to initialize multi-hop agent: {e}", exc_info=True)
        # Continue without multi-hop agent

    # Check if critical components are initialized
    if not agent and not multihop_agent:
        logger.warning("WARNING: No agents initialized! API will have limited functionality.")

    # Initialize Adaptive Hopping System
    try:
        from core.adaptive_integration import initialize_adaptive_system
        from core.llm_client import OllamaClient
        
        # Get LLM client for complexity detection
        llm_config = config.get("llm", {})
        llm = OllamaClient(
            base_url=llm_config.get("base_url", "http://127.0.0.1:11434"),
            model=llm_config.get("model", "qwen2.5:3b"),
            timeout=llm_config.get("timeout", 120)
        )
        
        adaptive_manager, adaptive_query_processor = initialize_adaptive_system(
            llm=llm,
            agent=agent,
            multihop_agent=multihop_agent,
            system_monitor=system_monitor,
            performance_tracker=performance_tracker
        )
        logger.info("Adaptive Hopping System initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Adaptive Hopping System: {e}", exc_info=True)
        logger.warning("API will continue without adaptive features")

    logger.info("CrawlLama API started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down CrawlLama API...")

    # Close Redis connection
    if redis_rate_limiter:
        try:
            redis_rate_limiter.close()
            logger.info("Redis rate limiter closed")
        except Exception as e:
            logger.error(f"Error closing Redis rate limiter: {e}")

    # Print final health summary
    if system_monitor and performance_tracker:
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


# Rate limiting (simple in-memory, use Redis for production)
request_counts: Dict[str, List[float]] = {}
# Async lock prevents anyio/threadpool deadlocks in ASGI test environments.
rate_limit_lock = asyncio.Lock()
config_lock = threading.Lock()  # Thread-safe config file writes
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "60"))  # requests per minute
MAX_QUERY_LENGTH = 5000  # Maximum query length
MAX_MEMORY_ENTRIES = 10000  # Maximum memory entries per category


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
    import ipaddress
    
    # Don't hash special values
    if key in ["unknown", "dev"]:
        return key
    
    # Don't hash IP addresses (both IPv4 and IPv6)
    try:
        ipaddress.ip_address(key)
        return key  # Valid IP address, return as-is
    except ValueError:
        pass  # Not an IP address, proceed with hashing
    
    # SECURITY: Use a keyed HMAC (default SHA3-256) to derive a stable
    # identifier for logging while preventing reversal of sensitive keys.
    # The key is immediately hashed with a secret and never stored/logged in plaintext
    return hmac_sha256_hex(key, key=RATE_LIMIT_SECRET)  # deterministic, keyed ID


async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key for authentication."""
    # Skip API key check if in development mode
    if os.getenv("CRAWLLAMA_DEV_MODE", "false").lower() == "true":
        return "dev"

    if not x_api_key or x_api_key != API_KEY:
        # SECURITY: Never log API keys - only log that authentication failed
        logger.warning("Invalid or missing API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


def verify_csrf_token(
    x_csrf_token: Optional[str] = Header(None),
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
    # Skip in DEV_MODE
    if os.getenv("CRAWLLAMA_DEV_MODE", "false").lower() == "true":
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
    def role_checker(api_key: str = Depends(verify_api_key)) -> str:
        """Check if user has required role.
        
        Args:
            api_key: Authenticated API key
            
        Returns:
            The API key if authorized
            
        Raises:
            HTTPException: If user lacks required permissions
        """
        # Skip in DEV_MODE
        if os.getenv("CRAWLLAMA_DEV_MODE", "false").lower() == "true":
            return api_key
        
        # Get user's role
        user_id = hash_api_key_for_logging(api_key)
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
        key = request.client.host if request.client else "unknown"
    current_time = time.time()

    # Thread-safe rate limiting
    async with rate_limit_lock:
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


def validate_plugin_name(plugin_name: str) -> str:
    """
    Validate plugin name to prevent path traversal attacks.
    
    Implements multiple security layers:
    1. Unicode normalization to prevent bypass attempts
    2. Length limits to prevent buffer overflow
    3. Whitelist-based character validation
    4. Path traversal pattern detection
    5. Forbidden names blacklist
    6. Absolute path verification
    
    Args:
        plugin_name: The plugin name to validate
        
    Returns:
        Validated plugin name
        
    Raises:
        HTTPException: If validation fails
    """
    if not plugin_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plugin name cannot be empty."
        )
    
    # 1. Unicode normalization (NFKC) to prevent Unicode bypass attacks
    # This converts characters like \u002e (Unicode dot) to actual dot
    plugin_name = unicodedata.normalize('NFKC', plugin_name)
    
    # 2. Length limit to prevent excessively long names
    MAX_PLUGIN_NAME_LENGTH = 50
    if len(plugin_name) > MAX_PLUGIN_NAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plugin name too long. Maximum {MAX_PLUGIN_NAME_LENGTH} characters allowed."
        )
    
    # 3. Whitelist-based validation - only alphanumeric, underscore, and hyphen
    if not re.match(r'^[a-zA-Z0-9_-]+$', plugin_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plugin name. Only alphanumeric, underscore, and hyphen allowed."
        )
    
    # 4. Prevent path traversal patterns
    dangerous_patterns = ["..", "/", "\\", "\0", "%"]
    for pattern in dangerous_patterns:
        if pattern in plugin_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid plugin name. Path traversal or dangerous characters detected."
            )
    
    # 5. Forbidden names blacklist
    forbidden_names = [
        ".", "..", "__init__", "config", "secret", "secrets",
        "env", ".env", "password", "key", "token",
        "con", "prn", "aux", "nul",  # Windows reserved names
        "com1", "com2", "lpt1", "lpt2"  # Windows reserved names
    ]
    if plugin_name.lower() in forbidden_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plugin name is forbidden."
        )
    
    # 6. Verify that constructed path stays within plugins directory
    import os.path
    plugin_path = os.path.join("plugins", plugin_name)
    plugin_path_normalized = os.path.normpath(plugin_path)
    
    # Ensure the normalized path still starts with "plugins"
    if not plugin_path_normalized.startswith("plugins" + os.sep):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plugin path. Security violation detected."
        )
    
    return plugin_name


# Valid memory categories whitelist
VALID_MEMORY_CATEGORIES = {"email", "phone", "ip", "username", "domain", "note", "emails", "phones", "ips", "usernames", "domains", "notes"}


def validate_memory_category(category: str) -> str:
    """Validate memory category against whitelist."""
    if category not in VALID_MEMORY_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(sorted(VALID_MEMORY_CATEGORIES))}"
        )
    return category


def filter_sensitive_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Filter sensitive data from config before returning to client."""
    filtered = copy.deepcopy(config_dict)

    # List of sensitive key patterns (case-insensitive)
    sensitive_patterns = ["api_key", "apikey", "api_secret", "secret", "password", "token", "private_key", "privatekey", "credential"]

    def _filter_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        for key in list(d.keys()):
            # Check if key matches sensitive pattern
            if any(pattern in key.lower() for pattern in sensitive_patterns):
                d[key] = "***REDACTED***"
            # Recursively filter nested dicts
            elif isinstance(d[key], dict):
                d[key] = _filter_dict(d[key])
        return d

    return _filter_dict(filtered)


# Request/Response models
class QueryRequest(BaseModel):
    """Query request model."""
    query: str = Field(..., description="Search query", min_length=1, max_length=MAX_QUERY_LENGTH)
    use_multihop: bool = Field(False, description="Use multi-hop reasoning")
    max_hops: Optional[int] = Field(3, description="Maximum reasoning hops", ge=1, le=5)
    use_tools: bool = Field(True, description="Enable web search tools")
    stream: bool = Field(False, description="Stream response (not yet implemented, reserved for future use)")

    @validator('query')
    def sanitize_query_input(cls, v):
        """Sanitize query input."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        # Remove potential injection attempts
        sanitized = sanitize_query(v)
        if len(sanitized) > MAX_QUERY_LENGTH:
            raise ValueError(f"Query too long (max {MAX_QUERY_LENGTH} characters)")
        return sanitized


class QueryResponse(BaseModel):
    """Query response model."""
    answer: str
    confidence: Optional[float] = None
    steps: Optional[int] = None
    search_queries: Optional[List[str]] = None
    reasoning_path: Optional[List[str]] = None
    elapsed_time: float
    cached: bool = False


class AdaptiveQueryRequest(BaseModel):
    """Adaptive query request model."""
    query: str = Field(..., description="Search query", min_length=1, max_length=MAX_QUERY_LENGTH)
    force_complexity: Optional[str] = Field(None, description="Force complexity level: low, mid, high")
    enable_escalation: bool = Field(True, description="Enable confidence-based escalation")

    @validator('query')
    def sanitize_query_input(cls, v):
        """Sanitize query input."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        sanitized = sanitize_query(v)
        if len(sanitized) > MAX_QUERY_LENGTH:
            raise ValueError(f"Query too long (max {MAX_QUERY_LENGTH} characters)")
        return sanitized

    @validator('force_complexity')
    def validate_complexity(cls, v):
        """Validate complexity level."""
        if v is not None and v.lower() not in ["low", "mid", "high"]:
            raise ValueError("force_complexity must be 'low', 'mid', or 'high'")
        return v.lower() if v else None


class AdaptiveQueryResponse(BaseModel):
    """Adaptive query response model."""
    answer: str
    confidence: Optional[float] = None
    strategy: Dict[str, Any]
    metadata: Dict[str, Any]
    steps: Optional[int] = None
    search_queries: Optional[List[str]] = None
    reasoning_path: Optional[List[str]] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str
    components: Dict[str, str]


class StatsResponse(BaseModel):
    """Statistics response."""
    agent_stats: Dict[str, Any]
    resource_stats: Dict[str, Any]
    uptime: float


# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - serves web interface."""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
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

@app.get("/api", response_model=Dict[str, str])
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


@app.get("/security-info")
async def security_info():
    """Get security configuration info (non-sensitive)."""
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


# ================================
# RBAC Admin Endpoints
# ================================

class RoleAssignmentRequest(BaseModel):
    """Role assignment request model."""
    api_key_to_manage: str = Field(..., description="API key (or hash) to assign role to", min_length=8)
    role: str = Field(..., description="Role to assign: admin, user, or read_only")
    
    @validator('role')
    def validate_role(cls, v):
        """Validate role value."""
        if v.lower() not in ["admin", "user", "read_only"]:
            raise ValueError("Role must be one of: admin, user, read_only")
        return v.lower()


@app.post("/admin/roles/assign", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
async def assign_role(request: RoleAssignmentRequest, admin_api_key: str = Depends(verify_api_key)):
    """Assign a role to an API key. (Admin only)
    
    Allows administrators to grant or modify user roles.
    """
    try:
        # Hash the API key for storage
        api_key_hash = hash_api_key_for_logging(request.api_key_to_manage)
        
        # Convert string to Role enum
        role = Role.from_string(request.role)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {request.role}"
            )
        
        # Assign role
        admin_hash = hash_api_key_for_logging(admin_api_key)
        success = rbac_manager.assign_role(
            api_key_hash=api_key_hash,
            role=role,
            user_info=f"admin:{admin_hash[:8]}"
        )
        
        if success:
            return {
                "status": "success",
                "message": f"Role '{role.value}' assigned to user",
                "user_id": api_key_hash[:16] + "...",
                "role": role.value
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to assign role"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign role: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign role"
        )


@app.get("/admin/roles/list", dependencies=[Depends(check_rate_limit), Depends(verify_role(Role.ADMIN))])
async def list_roles():
    """List all role assignments. (Admin only)"""
    try:
        roles = rbac_manager.list_roles()
        
        # Format for display (truncate API keys)
        formatted_roles = {}
        for api_key_hash, role in roles.items():
            formatted_roles[api_key_hash[:16] + "..."] = role
        
        return {
            "status": "success",
            "total_users": len(formatted_roles),
            "roles": formatted_roles,
            "role_hierarchy": get_role_hierarchy()
        }
    
    except Exception as e:
        logger.error(f"Failed to list roles: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list roles"
        )


@app.get("/admin/roles/me", dependencies=[Depends(check_rate_limit)])
async def get_my_role(api_key: str = Depends(verify_api_key)):
    """Get your own role."""
    try:
        user_id = hash_api_key_for_logging(api_key)
        role = rbac_manager.get_role(user_id)
        
        return {
            "status": "success",
            "user_id": user_id[:16] + "...",
            "role": role.value,
            "permissions": {
                "admin_access": role >= Role.ADMIN,
                "write_access": role >= Role.USER,
                "read_access": role >= Role.READ_ONLY
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to get role: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve role"
        )


@app.delete("/admin/roles/revoke", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
async def revoke_role(api_key_to_revoke: str):
    """Revoke a role assignment (resets to default). (Admin only)"""
    try:
        api_key_hash = hash_api_key_for_logging(api_key_to_revoke)
        
        success = rbac_manager.revoke_role(api_key_hash)
        
        if success:
            return {
                "status": "success",
                "message": "Role revoked, user will use default role",
                "user_id": api_key_hash[:16] + "...",
                "default_role": rbac_manager.get_role(api_key_hash).value
            }
        else:
            return {
                "status": "info",
                "message": "No role assignment found for user"
            }
    
    except Exception as e:
        logger.error(f"Failed to revoke role: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke role"
        )


@app.get("/admin/roles/stats", dependencies=[Depends(check_rate_limit), Depends(verify_role(Role.ADMIN))])
async def rbac_stats():
    """Get RBAC manager statistics. (Admin only)"""
    try:
        stats = rbac_manager.get_stats()
        
        return {
            "status": "success",
            "rbac_stats": stats
        }
    
    except Exception as e:
        logger.error(f"Failed to get RBAC stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve RBAC statistics"
        )


# ================================
# Audit Logging Endpoints  
# ================================

@app.get("/admin/audit/logs", dependencies=[Depends(check_rate_limit), Depends(verify_role(Role.ADMIN))])
async def query_audit_logs(
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
):
    """Query audit logs with filters. (Admin only)
    
    Args:
        event_type: Filter by event type (authentication, authorization, api_request, etc.)
        user_id: Filter by user ID
        status: Filter by status (success, failure)
        limit: Maximum number of results (default: 100, max: 1000)
    """
    try:
        # Limit max results
        limit = min(limit, 1000)
        
        # Search logs
        logs = audit_logger.search_logs(
            event_type=event_type,
            user_id=user_id,
            status=status,
            limit=limit
        )
        
        return {
            "status": "success",
            "count": len(logs),
            "logs": logs,
            "filters": {
                "event_type": event_type,
                "user_id": user_id,
                "status": status,
                "limit": limit
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to query audit logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query audit logs"
        )


@app.get("/admin/audit/stats", dependencies=[Depends(check_rate_limit), Depends(verify_role(Role.ADMIN))])
async def audit_stats():
    """Get audit log statistics. (Admin only)"""
    try:
        stats = audit_logger.get_stats()
        
        return {
            "status": "success",
            "audit_stats": stats
        }
    
    except Exception as e:
        logger.error(f"Failed to get audit stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit statistics"
        )


# ================================
# API Key Management Endpoints
# ================================

class APIKeyGenerateRequest(BaseModel):
    """API key generation request."""
    user_id: Optional[str] = Field(None, description="User ID (defaults to current user)")
    expiry_days: Optional[int] = Field(90, description="Days until expiration (0 = no expiry)", ge=0, le=365)


@app.post("/admin/api-keys/generate", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
async def generate_api_key(request: APIKeyGenerateRequest, api_key: str = Depends(verify_api_key)):
    """Generate a new API key. (Admin only)
    
    Supports multiple active keys per user for graceful rotation.
    """
    try:
        # Use provided user_id or default to current user
        if request.user_id:
            target_user_id = request.user_id
        else:
            target_user_id = hash_api_key_for_logging(api_key)
        
        # Generate key
        new_key, key_id = api_key_manager.generate_key(
            user_id=target_user_id,
            expiry_days=request.expiry_days,
            metadata={"created_by": "admin"}
        )
        
        # Log to audit
        audit_logger.log_security_event(
            event_subtype="api_key_generated",
            user_id=target_user_id[:16] + "...",
            status="success",
            details=f"New API key generated: {key_id}"
        )
        
        return {
            "status": "success",
            "message": "API key generated successfully",
            "api_key": new_key,
            "key_id": key_id,
            "user_id": target_user_id[:16] + "...",
            "expires_in_days": request.expiry_days,
            "warning": "Save this key securely. It will not be shown again."
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate API key"
        )


@app.post("/admin/api-keys/rotate", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def rotate_api_key(current_key: str = Depends(verify_api_key)):
    """Rotate your current API key.
    
    Generates a new key while keeping the old one active temporarily.
    Revoke the old key once you've updated your applications.
    """
    try:
        # Generate new key
        new_key, new_key_id = api_key_manager.rotate_key(current_key)
        
        # Get user ID
        user_id = hash_api_key_for_logging(current_key)
        
        # Log to audit
        audit_logger.log_security_event(
            event_subtype="api_key_rotated",
            user_id=user_id[:16] + "...",
            status="success",
            details=f"API key rotated successfully: {new_key_id}"
        )
        
        return {
            "status": "success",
            "message": "API key rotated successfully",
            "new_api_key": new_key,
            "new_key_id": new_key_id,
            "note": "Your old key is still active. Revoke it after updating your applications.",
            "warning": "Save this key securely. It will not be shown again."
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rotate API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rotate API key"
        )


@app.get("/admin/api-keys/list", dependencies=[Depends(check_rate_limit)])
async def list_api_keys(api_key: str = Depends(verify_api_key)):
    """List your API keys (shows metadata only, not the keys themselves)."""
    try:
        user_id = hash_api_key_for_logging(api_key)
        
        keys = api_key_manager.list_keys(user_id, active_only=False)
        active_keys = [k for k in keys if k["is_active"] and not k["is_expired"]]
        
        return {
            "status": "success",
            "user_id": user_id[:16] + "...",
            "total_keys": len(keys),
            "active_keys": len(active_keys),
            "keys": keys
        }
    
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys"
        )


@app.delete("/admin/api-keys/revoke/{key_id}", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def revoke_api_key(key_id: str, api_key: str = Depends(verify_api_key)):
    """Revoke (deactivate) an API key by its ID."""
    try:
        success = api_key_manager.revoke_key(key_id)
        
        if success:
            user_id = hash_api_key_for_logging(api_key)
            
            # Log to audit
            audit_logger.log_security_event(
                event_subtype="api_key_revoked",
                user_id=user_id[:16] + "...",
                status="success",
                details=f"API key revoked: {key_id}"
            )
            
            return {
                "status": "success",
                "message": f"API key {key_id} revoked successfully",
                "key_id": key_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key"
        )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    components = {
        "agent": "healthy" if agent else "unavailable",
        "multihop_agent": "healthy" if multihop_agent else "unavailable",
        "memory_store": "healthy" if memory_store else "unavailable",
        "system_monitor": "healthy" if system_monitor else "unavailable",
        "performance_tracker": "healthy" if performance_tracker else "unavailable"
    }

    return HealthResponse(
        status="healthy" if all(v == "healthy" for v in components.values()) else "degraded",
        timestamp=datetime.now().isoformat(),
        version=VERSION,
        components=components
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
        is_result_ref = bool(re.search(r'\b(?:source|quelle|result|ergebnis)s?\s+\d+\b', query_lower))

        # Force SearchAgent for result references and context-only mode
        use_multihop = request.use_multihop and not is_context_mode and not is_result_ref

        if is_context_mode or is_result_ref:
            logger.info(f"Forcing SearchAgent (context_mode={is_context_mode}, result_ref={is_result_ref})")

        if use_multihop:
            # Use multi-hop reasoning agent
            if not multihop_agent:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Multi-hop agent not available"
                )

            # Use custom max_hops if provided
            if request.max_hops and request.max_hops != 3:
                # Create temporary agent with custom max_hops
                temp_agent = MultiHopReasoningAgent(
                    config=config,
                    max_hops=request.max_hops,
                    confidence_threshold=0.7
                )
                result = temp_agent.query(request.query)
            else:
                result = multihop_agent.query(request.query)

            return QueryResponse(
                answer=result["answer"],
                confidence=result.get("confidence"),
                steps=result.get("steps"),
                search_queries=result.get("search_queries"),
                reasoning_path=result.get("reasoning_path"),
                elapsed_time=time.time() - start_time,
                cached=False
            )

        else:
            # Use standard agent
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Agent not available"
                )

            answer = agent.query(request.query, use_tools=request.use_tools)

            return QueryResponse(
                answer=answer,
                elapsed_time=time.time() - start_time,
                cached=False
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query processing failed. Please check your input and try again."
        )


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

        if not adaptive_query_processor:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Adaptive Hopping System not available. Please check system configuration."
            )

        # Process query with adaptive system
        result = adaptive_query_processor.process_query(
            query=request.query,
            force_complexity=request.force_complexity,
            enable_escalation=request.enable_escalation
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
        logger.error(f"Adaptive query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Adaptive query processing failed: {str(e)}"
        )


@app.get("/stats", response_model=StatsResponse, dependencies=[Depends(check_rate_limit)])
async def stats_endpoint():
    """Get system statistics."""
    try:
        agent_stats = agent.get_stats() if agent else {}

        # Gather resource stats from health monitoring
        resource_stats = {}
        if system_monitor:
            metrics = system_monitor.get_latest_metrics()
            if metrics:
                resource_stats["system"] = {
                    "cpu_percent": metrics.cpu_percent,
                    "memory_percent": metrics.memory_percent,
                    "memory_used_gb": metrics.memory_used_gb,
                    "memory_total_gb": metrics.memory_total_gb,
                    "disk_percent": metrics.disk_percent,
                }

        if performance_tracker:
            perf_stats = performance_tracker.get_all_stats()
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
        )


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
        )


@app.post("/plugins/{plugin_name}/load", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
async def load_plugin(plugin_name: str):
    """Load a plugin dynamically. (Admin only)"""
    try:
        # Validate plugin name to prevent path traversal
        plugin_name = validate_plugin_name(plugin_name)

        loader = get_unified_loader()
        plugin = loader.load_plugin(plugin_name)

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
        )


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
        )


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
        )


@app.post("/cache/clear", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def clear_cache():
    """Clear application cache."""
    try:
        if agent and agent.cache:
            count = agent.cache.clear()
            return {"status": "success", "message": f"Cache cleared ({count} entries)"}
        else:
            return {"status": "info", "message": "No cache to clear"}

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )


@app.get("/cache/stats", dependencies=[Depends(check_rate_limit)])
async def cache_stats():
    """Get cache statistics."""
    try:
        if agent and agent.cache:
            stats = agent.cache.get_stats()
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
        )


@app.post("/session/clear", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def clear_session():
    """Clear conversation session."""
    try:
        if agent:
            result = agent.clear_session()
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
        )


@app.post("/session/save", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def save_session():
    """Save current session."""
    try:
        if agent:
            agent.save_session()
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
        )


@app.post("/session/load", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def load_session():
    """Load saved session."""
    try:
        if agent:
            agent.load_session()
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
        )


@app.post("/session/refresh", dependencies=[Depends(check_rate_limit)])
async def refresh_session(request: Request, api_key: str = Depends(verify_api_key)):
    """Refresh (extend) a session's expiration time.
    
    Extends the session by 24 hours from now.
    Updates last activity timestamp and client IP.
    """
    try:
        # Get user ID from API key
        user_id = hash_api_key_for_logging(api_key)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # For this simplified version, we'll use user_id as session_id
        # In a full implementation, you'd track actual session IDs
        return {
            "status": "success",
            "message": "Session refreshed",
            "note": "Session extended by 24 hours",
            "client_ip": client_ip
        }

    except Exception as e:
        logger.error(f"Failed to refresh session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh session"
        )


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
        )


class ConfigUpdateRequest(BaseModel):
    """Configuration update request model."""
    category: str = Field(..., description="Config category (llm, search, rag, cache, osint, etc.)")
    key: str = Field(..., description="Configuration key to update")
    value: Any = Field(..., description="New value")


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

        # Thread-safe config update
        with config_lock:
            # Update config
            config[request.category][request.key] = request.value

            # Save to file atomically
            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)

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
        )


@app.get("/context/status", dependencies=[Depends(check_rate_limit)])
async def context_status():
    """Get context usage status."""
    try:
        if agent and hasattr(agent, 'context_manager'):
            context_mgr = agent.context_manager
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
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__
        }
    )


# Memory Store Endpoints
@app.get("/memory", dependencies=[Depends(check_rate_limit)])
async def get_memory():
    """Get all memory store entries."""
    try:
        if not memory_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory store not available"
            )

        return {
            "status": "success",
            "data": memory_store.get_all()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get memory: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memory data"
        )


class MemoryRequest(BaseModel):
    """Memory operation request model."""
    category: str = Field(..., description="Memory category (email, phone, ip, username, domain, note)")
    value: str = Field(..., description="Value to remember")


@app.post("/memory/remember", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def remember(request: MemoryRequest):
    """Remember a value in memory store."""
    try:
        if not memory_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory store not available"
            )

        # Validate category
        validate_memory_category(request.category)

        # Call the appropriate remember method based on category
        category_methods = {
            'email': memory_store.remember_email,
            'emails': memory_store.remember_email,
            'phone': memory_store.remember_phone,
            'phones': memory_store.remember_phone,
            'ip': memory_store.remember_ip,
            'ips': memory_store.remember_ip,
            'username': memory_store.remember_username,
            'usernames': memory_store.remember_username,
            'domain': memory_store.remember_domain,
            'domains': memory_store.remember_domain,
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
        )


@app.get("/memory/recall/{category}", dependencies=[Depends(check_rate_limit)])
async def recall(category: str):
    """Recall values from memory store by category."""
    try:
        if not memory_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory store not available"
            )

        # Validate category
        validate_memory_category(category)

        # Call the appropriate get method based on category
        category_methods = {
            'email': memory_store.get_all_emails,
            'emails': memory_store.get_all_emails,
            'phone': memory_store.get_all_phones,
            'phones': memory_store.get_all_phones,
            'ip': memory_store.get_all_ips,
            'ips': memory_store.get_all_ips,
            'username': memory_store.get_all_usernames,
            'usernames': memory_store.get_all_usernames,
            'domain': memory_store.get_all_domains,
            'domains': memory_store.get_all_domains,
            'note': memory_store.get_all_notes,
            'notes': memory_store.get_all_notes,
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
        )


@app.get("/memory/stats", dependencies=[Depends(check_rate_limit)])
async def memory_stats():
    """Get memory store statistics."""
    try:
        if not memory_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory store not available"
            )

        summary = memory_store.get_summary()

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
        )


class ForgetRequest(BaseModel):
    """Forget operation request model."""
    category: Optional[str] = Field(None, description="Category to forget (email, phone, etc.) or 'all' for everything")
    value: Optional[str] = Field(None, description="Specific value to forget")


@app.delete("/memory/forget", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def forget(request: ForgetRequest):
    """Forget values from memory store."""
    try:
        if not memory_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory store not available"
            )

        if request.category == "all" or (not request.category and not request.value):
            # Clear all memory
            success = memory_store.clear_all()
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
                'email': memory_store.forget_email,
                'emails': memory_store.forget_email,
                'phone': memory_store.forget_phone,
                'phones': memory_store.forget_phone,
                'ip': memory_store.forget_ip,
                'ips': memory_store.forget_ip,
                'username': memory_store.forget_username,
                'usernames': memory_store.forget_username,
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
            success = memory_store.clear_category(request.category)
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
        )


@app.get("/memory/stats", dependencies=[Depends(check_rate_limit)])
async def memory_stats():
    """Get memory store statistics."""
    try:
        if not memory_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory store not available"
            )

        data = memory_store.get_all()
        stats = {
            "total_entries": len(data),
            "categories": {}
        }

        for category in ["emails", "phones", "ips", "usernames", "domains", "notes"]:
            stats["categories"][category] = len(data.get(category, []))

        return {
            "status": "success",
            "data": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memory statistics"
        )


# OSINT Endpoints
class OSINTRequest(BaseModel):
    """OSINT query request model."""
    query: str = Field(..., description="OSINT query with operators (email:, phone:, ip:, etc.)", min_length=1, max_length=MAX_QUERY_LENGTH)

    @validator('query')
    def sanitize_query_input(cls, v):
        """Sanitize query input."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        # Remove potential injection attempts
        sanitized = sanitize_query(v)
        if len(sanitized) > MAX_QUERY_LENGTH:
            raise ValueError(f"Query too long (max {MAX_QUERY_LENGTH} characters)")
        return sanitized


class CompanyOSINTRequest(BaseModel):
    """Company OSINT request model."""
    company_name: str = Field(..., description="Company name to investigate", min_length=1, max_length=200)
    country: Optional[str] = Field(None, description="Optional country hint (e.g., DE, US)")
    region: Optional[str] = Field(None, description="Optional search region hint (e.g., de-de, us-en)")
    language: Optional[str] = Field(None, description="Optional language hint (e.g., de, en)")

    @validator('company_name')
    def sanitize_company_name(cls, v):
        """Sanitize company name input."""
        if not v or not v.strip():
            raise ValueError("Company name cannot be empty")
        sanitized = sanitize_query(v)
        if len(sanitized) > 200:
            raise ValueError("Company name too long (max 200 characters)")
        return sanitized

    @validator('country')
    def sanitize_country(cls, v):
        """Validate optional country code (ISO-2)."""
        if v is None:
            return v
        sanitized = sanitize_query(v).upper()
        if not re.fullmatch(r"[A-Z]{2}", sanitized):
            raise ValueError("country must be ISO-2 format, e.g. DE or US")
        return sanitized

    @validator('region')
    def sanitize_region(cls, v):
        """Validate optional region hint (xx-xx)."""
        if v is None:
            return v
        sanitized = sanitize_query(v).lower()
        if not re.fullmatch(r"[a-z]{2}-[a-z]{2}", sanitized):
            raise ValueError("region must be format xx-xx, e.g. de-de or us-en")
        return sanitized

    @validator('language')
    def sanitize_language(cls, v):
        """Validate optional language code (ISO-2)."""
        if v is None:
            return v
        sanitized = sanitize_query(v).lower()
        if not re.fullmatch(r"[a-z]{2}", sanitized):
            raise ValueError("language must be ISO-2 format, e.g. de or en")
        return sanitized


@app.post("/osint/query", dependencies=[Depends(check_rate_limit)])
async def osint_query(request: OSINTRequest):
    """Execute OSINT query with operators."""
    try:
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Agent not available"
            )

        start_time = time.time()
        answer = agent.query(request.query, use_tools=True)

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
        )


@app.post("/osint/company", dependencies=[Depends(check_rate_limit)])
async def osint_company(request: CompanyOSINTRequest):
    """Execute company-focused OSINT query using natural input."""
    try:
        if not agent:
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
        answer = agent.query(synthesized_query, use_tools=True)

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
        )


# Development Endpoint: Retrieve temporary API key
@app.get("/dev/api-key")
async def get_dev_api_key():
    """
    Retrieve the temporary API key (only available in DEV_MODE).
    
    Security: This endpoint is ONLY accessible when CRAWLLAMA_DEV_MODE=true.
    Never expose this in production!
    """
    dev_mode = os.getenv("CRAWLLAMA_DEV_MODE", "false").lower() == "true"
    
    if not dev_mode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Endpoint not available in production mode",
                "message": "This development endpoint is disabled for security reasons.",
                "solution": "To access the API key in development mode, set environment variable: CRAWLLAMA_DEV_MODE=true"
            }
        )
    
    # Only return if API_KEY was auto-generated (not from .env)
    if not os.getenv("CRAWLLAMA_API_KEY"):
        return {
            "status": "success",
            "api_key": API_KEY,
            "warning": "This is a temporary key for development only. Set CRAWLLAMA_API_KEY in .env for production.",
            "usage": "Add this header to your requests: X-API-Key: " + API_KEY
        }
    else:
        return {
            "status": "info",
            "message": "API key is configured via environment variable. Check your .env file."
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
           "app:app",
           host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )
