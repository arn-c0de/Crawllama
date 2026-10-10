"""Plugin management and tool listing endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import (
    check_rate_limit,
    verify_csrf_token,
    verify_role,
)
from api.validation import validate_plugin_name
from core.rbac_manager import Role
from core.unified_loader import get_unified_loader

logger = logging.getLogger("crawllama")

router = APIRouter()


@router.get("/plugins", dependencies=[Depends(check_rate_limit)])
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


@router.post("/plugins/{plugin_name}/load", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
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


@router.post("/plugins/{plugin_name}/unload", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
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


@router.get("/tools", dependencies=[Depends(check_rate_limit)])
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

