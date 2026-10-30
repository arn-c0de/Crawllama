"""Configuration endpoints (admin only)."""
import asyncio
import copy
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from api import runtime
from api.dependencies import check_rate_limit, verify_csrf_token, verify_role
from api.models import ConfigUpdateRequest
from api.validation import filter_sensitive_config
from core.rbac_manager import Role
from utils.file_utils import write_json_atomic

logger = logging.getLogger("crawllama")

router = APIRouter()


@router.get("/config", dependencies=[Depends(check_rate_limit), Depends(verify_role(Role.ADMIN))])
async def get_config():
    """Get current configuration (sensitive values redacted)."""
    try:
        # Thread-safe config read
        with runtime.config_lock:
            # Filter sensitive data before returning
            filtered_config = filter_sensitive_config(runtime.config)

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


def _is_compatible_config_value(current: Any, new: Any) -> bool:
    """A new config value must keep the type of the existing one (int may become float)."""
    if current is None:
        return True
    if isinstance(current, bool) or isinstance(new, bool):
        return isinstance(current, bool) and isinstance(new, bool)
    if isinstance(current, (int, float)):
        return isinstance(new, (int, float))
    return isinstance(new, type(current))


@router.patch("/config", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
async def update_config(request: ConfigUpdateRequest):
    """Update configuration setting. (Admin only)"""
    config = runtime.config
    try:
        if not runtime.config_loaded_from_file:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="config.json could not be loaded at startup; refusing to overwrite it"
            )

        if request.category not in config or not isinstance(config[request.category], dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category: {request.category}"
            )

        if request.key not in config[request.category]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid key: {request.key} in category {request.category}"
            )

        current_value = config[request.category][request.key]
        if not _is_compatible_config_value(current_value, request.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid value type for {request.category}.{request.key}: "
                       f"expected {type(current_value).__name__}"
            )

        # Thread-safe config update; the write is atomic (tmp + rename) so a
        # crash cannot truncate config.json, and runs off the event loop.
        # The file is written from a copy first and the live config is only
        # changed once the write succeeded.
        def _update_and_write_config():
            with runtime.config_lock:
                updated = copy.deepcopy(config)
                updated[request.category][request.key] = request.value
                write_json_atomic("config.json", updated)
                config[request.category][request.key] = request.value

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
