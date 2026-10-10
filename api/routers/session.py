"""Cache and session management endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api import runtime
from api.dependencies import (
    check_rate_limit,
    verify_csrf_token,
)

logger = logging.getLogger("crawllama")

router = APIRouter()


@router.post("/cache/clear", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
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


@router.get("/cache/stats", dependencies=[Depends(check_rate_limit)])
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


@router.post("/session/clear", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
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


@router.post("/session/save", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
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


@router.post("/session/load", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
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

