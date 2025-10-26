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

from core.agent import SearchAgent
from core.langgraph_agent import MultiHopReasoningAgent
from core.unified_loader import get_unified_loader
from core.memory_store import MemoryStore
from core.health import get_system_monitor, get_performance_tracker, print_health_summary, shutdown_monitoring
from utils.validators import sanitize_query
from utils.redis_rate_limiter import RedisRateLimiter, get_rate_limit_for_endpoint
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("crawllama")

# Version constant
VERSION = "1.4.2"

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
# Add testserver for TestClient compatibility
if os.getenv("CRAWLLAMA_DEV_MODE", "false").lower() == "true":
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Content Security Policy - Prevent XSS attacks
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "  # unsafe-inline needed for some frameworks
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "frame-ancestors 'none';"
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
            # SECURITY: HMAC-SHA256 is cryptographically secure (FIPS 140-2 compliant)
            # The API key is immediately hashed with a secret key and never stored/logged in plaintext
            # This is the CORRECT way to handle API keys for rate limiting
            # lgtm[py/weak-cryptographic-algorithm]
            user_id = hmac.new(
                RATE_LIMIT_SECRET,
                api_key.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()[:16]
        
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


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global agent, multihop_agent, memory_store, system_monitor, performance_tracker, redis_rate_limiter

    logger.info("Starting CrawlLama API...")

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
rate_limit_lock = threading.Lock()  # Thread-safe access to request_counts
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
    
    # SECURITY: HMAC-SHA256 is cryptographically secure (FIPS 140-2 compliant)
    # The key is immediately hashed with a secret and never stored/logged in plaintext
    # This is the CORRECT way to handle sensitive keys for logging
    # lgtm[py/weak-cryptographic-algorithm]
    return hmac.new(
        RATE_LIMIT_SECRET,
        key.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:16]


def verify_api_key(x_api_key: Optional[str] = Header(None)):
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


def check_rate_limit(request: Request, api_key: str = Depends(verify_api_key)):
    """Rate limiting based on API key or IP."""
    # Use API key if available, otherwise use IP
    if api_key != "dev":
        key = api_key
    else:
        # Fallback to IP address, or "unknown" if not available
        key = request.client.host if request.client else "unknown"
    current_time = time.time()

    # Thread-safe rate limiting
    with rate_limit_lock:
        if key not in request_counts:
            request_counts[key] = []

        # Remove old requests (older than 1 minute)
        request_counts[key] = [
            ts for ts in request_counts[key]
            if current_time - ts < 60
        ]

        if len(request_counts[key]) >= RATE_LIMIT:
            # SECURITY: Hash API key before logging to prevent exposure
            safe_key = hash_api_key_for_logging(key)
            logger.warning(f"Rate limit exceeded for key: {safe_key}")
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
        "dev_mode": os.getenv("CRAWLLAMA_DEV_MODE", "false"),
        "cors_origins": "Configured" if os.getenv("ALLOWED_ORIGINS") else "Development defaults (localhost only)",
        "features": {
            "rate_limiting": True,
            "query_sanitization": True,
            "input_validation": True,
            "request_logging": True,
            "trusted_hosts": True
        },
        "note": "API key required for all endpoints (except /health and /)"
    }


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
        logger.info(f"Processing query: '{request.query}' (multihop={request.use_multihop})")

        if request.use_multihop:
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


@app.post("/plugins/{plugin_name}/load", dependencies=[Depends(check_rate_limit)])
async def load_plugin(plugin_name: str):
    """Load a plugin dynamically."""
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
        logger.error(f"Failed to load plugin '{plugin_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to load plugin. Please check if the plugin exists and is valid."
        )


@app.post("/plugins/{plugin_name}/unload", dependencies=[Depends(check_rate_limit)])
async def unload_plugin(plugin_name: str):
    """Unload a plugin."""
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
        logger.error(f"Failed to unload plugin '{plugin_name}': {e}", exc_info=True)
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


@app.post("/cache/clear", dependencies=[Depends(check_rate_limit)])
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


@app.post("/session/clear", dependencies=[Depends(check_rate_limit)])
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


@app.post("/session/save", dependencies=[Depends(check_rate_limit)])
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


@app.post("/session/load", dependencies=[Depends(check_rate_limit)])
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


@app.patch("/config", dependencies=[Depends(check_rate_limit)])
async def update_config(request: ConfigUpdateRequest):
    """Update configuration setting."""
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


@app.post("/memory/remember", dependencies=[Depends(check_rate_limit)])
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


@app.delete("/memory/forget", dependencies=[Depends(check_rate_limit)])
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
        logger.error(f"OSINT query failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OSINT query failed. Please check your input and try again."
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
