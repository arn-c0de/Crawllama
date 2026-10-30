"""App-level endpoints: web UI, API info, health, stats, CSRF token, dev key."""
import asyncio
import logging
import os
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

from _version import __version__ as VERSION
from api import runtime
from api.constants import MAX_MEMORY_ENTRIES, MAX_QUERY_LENGTH
from api.dependencies import check_rate_limit, verify_api_key
from api.models import HealthResponse, StatsResponse
from api.security_config import API_KEY, RATE_LIMIT, client_ip, hash_api_key_for_logging, is_dev_mode
from core.csrf_manager import get_csrf_manager
from core.rbac_manager import get_role_hierarchy

logger = logging.getLogger("crawllama")

router = APIRouter()

API_INFO = {
    "name": "CrawlLama API",
    "version": VERSION,
    "description": "AI-powered web research agent",
    "docs": "/docs",
    "health": "/health",
    "security": "API Key required (set X-API-Key header or CRAWLLAMA_DEV_MODE=true)",
}


@router.get("/", response_class=HTMLResponse)
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
        return JSONResponse(API_INFO)

@router.get("/api", response_model=dict[str, str])
async def api_info():
    """API information endpoint."""
    return API_INFO


@router.get("/security-info", dependencies=[Depends(verify_api_key)])
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


@router.post("/csrf-token")
async def get_csrf_token(api_key: str = Depends(verify_api_key)):
    """Generate a CSRF token for the authenticated user.
    
    CSRF tokens are required for all state-changing operations (POST/PUT/PATCH/DELETE).
    Include the token in the X-CSRF-Token header for protected requests.
    
    Tokens expire after 1 hour by default.
    """
    # Use hashed API key as user ID
    user_id = hash_api_key_for_logging(api_key)
    
    # Generate token
    csrf_manager = get_csrf_manager()
    token = csrf_manager.generate_token(user_id)
    
    return {
        "csrf_token": token,
        "expires_in": csrf_manager.token_expiry,
        "usage": "Include this token in X-CSRF-Token header for POST/PUT/PATCH/DELETE requests",
        "note": "Token is bound to your API key and expires after the specified time"
    }


@router.get("/health", response_model=HealthResponse)
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


@router.get("/stats", response_model=StatsResponse, dependencies=[Depends(check_rate_limit)])
async def stats_endpoint(request: Request):
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
            uptime=time.time() - request.app.state.start_time if hasattr(request.app.state, 'start_time') else 0
        )

    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        ) from e


# Development Endpoint: Retrieve temporary API key
@router.get("/dev/api-key")
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
