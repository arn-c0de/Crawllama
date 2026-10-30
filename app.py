"""FastAPI application for CrawlLama - Production-ready API."""
import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime

import dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api import runtime
from api.constants import MAX_MEMORY_ENTRIES, MAX_QUERY_LENGTH
from api.dependencies import (
    check_rate_limit,
    verify_api_key,
)
from api.middleware import install_middleware
from api.models import (
    HealthResponse,
    StatsResponse,
)
from api.routers.admin import router as admin_router
from api.routers.config import router as config_router
from api.routers.memory import router as memory_router
from api.routers.osint import router as osint_router
from api.routers.plugins import router as plugins_router
from api.routers.query import router as query_router
from api.routers.session import router as session_router
from api.security_config import (
    API_KEY,
    RATE_LIMIT,
    RATE_LIMIT_SECRET_EPHEMERAL,
    _is_loopback_host,
    client_ip,
    hash_api_key_for_logging,
    is_dev_mode,
)
from api.sessions import PrincipalSessions
from core.agent import SearchAgent
from core.api_key_manager import get_api_key_manager
from core.audit_logger import get_audit_logger
from core.csrf_manager import get_csrf_manager
from core.health import get_performance_tracker, get_system_monitor, print_health_summary, shutdown_monitoring
from core.langgraph_agent import (
    MultiHopReasoningAgent,
    create_multihop_agent,
)
from core.memory_store import MemoryStore, get_memory_store
from core.rbac_manager import Role, get_rbac_manager, get_role_hierarchy
from utils.redis_rate_limiter import RedisRateLimiter
from utils.tor_mode import TorError, initialize_tor_mode

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

# Load configuration (shared with the routers through api.runtime)
try:
    with open("config.json", encoding="utf-8") as f:
        config = json.load(f)
    runtime.config_loaded_from_file = True
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    config = {
        "llm": {"model": "qwen2.5:3b"},
        "cache": {"enabled": True}
    }
    # PATCH /config must never write this fallback skeleton over config.json
    runtime.config_loaded_from_file = False
runtime.config = config


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
        # Use the process-wide singleton: a second instance would hold its own
        # copy of memory.json and overwrite the agent's changes (and vice versa)
        store = get_memory_store()
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
    runtime.system_monitor, runtime.performance_tracker = _create_health_monitoring()
    runtime.memory_store = _create_memory_store()
    runtime.agent = _create_standard_agent()
    # One conversation session per principal (API clients never share history)
    runtime.sessions = PrincipalSessions(
        base_dir=config.get("paths", {}).get("sessions_dir", "data/sessions")
    )
    runtime.multihop_agent = _create_multihop_agent()

    # Check if critical components are initialized
    if not runtime.agent and not runtime.multihop_agent:
        logger.warning("WARNING: No agents initialized! API will have limited functionality.")

    runtime.adaptive_manager, runtime.adaptive_query_processor = _create_adaptive_system(
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


install_middleware(app)


# Mount extracted endpoint routers
app.include_router(admin_router)
app.include_router(osint_router)
app.include_router(plugins_router)
app.include_router(session_router)
app.include_router(memory_router)
app.include_router(query_router)
app.include_router(config_router)


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
    client_host = client_ip(request, default="")
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
