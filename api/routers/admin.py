"""Admin endpoints: RBAC roles, audit logs and API-key management.

Extracted from app.py into a router. Mounted via ``app.include_router`` so the
paths and dependencies are unchanged. The manager singletons are fetched via
their ``get_*`` accessors (same instances the rest of the app uses).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import (
    check_rate_limit,
    verify_api_key,
    verify_csrf_token,
    verify_role,
)
from api.models import APIKeyGenerateRequest, RoleAssignmentRequest
from api.security_config import _short_id, hash_api_key_for_logging
from core.api_key_manager import get_api_key_manager
from core.audit_logger import get_audit_logger
from core.rbac_manager import Role, get_rbac_manager, get_role_hierarchy

logger = logging.getLogger("crawllama")

rbac_manager = get_rbac_manager()
api_key_manager = get_api_key_manager()
audit_logger = get_audit_logger()

router = APIRouter()


@router.post("/admin/roles/assign", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
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
                "user_id": _short_id(api_key_hash),
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
        ) from e


@router.get("/admin/roles/list", dependencies=[Depends(check_rate_limit), Depends(verify_role(Role.ADMIN))])
async def list_roles():
    """List all role assignments. (Admin only)"""
    try:
        roles = rbac_manager.list_roles()
        
        # Format for display (truncate API keys)
        formatted_roles = {}
        for api_key_hash, role in roles.items():
            formatted_roles[_short_id(api_key_hash)] = role
        
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
        ) from e


@router.get("/admin/roles/me", dependencies=[Depends(check_rate_limit)])
async def get_my_role(api_key: str = Depends(verify_api_key)):
    """Get your own role."""
    try:
        user_id = hash_api_key_for_logging(api_key)
        role = rbac_manager.get_role(user_id)
        
        return {
            "status": "success",
            "user_id": _short_id(user_id),
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
        ) from e


@router.delete("/admin/roles/revoke", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
async def revoke_role(api_key_to_revoke: str):
    """Revoke a role assignment (resets to default). (Admin only)"""
    try:
        api_key_hash = hash_api_key_for_logging(api_key_to_revoke)
        
        success = rbac_manager.revoke_role(api_key_hash)
        
        if success:
            return {
                "status": "success",
                "message": "Role revoked, user will use default role",
                "user_id": _short_id(api_key_hash),
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
        ) from e


@router.get("/admin/roles/stats", dependencies=[Depends(check_rate_limit), Depends(verify_role(Role.ADMIN))])
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
        ) from e


# ================================
# Audit Logging Endpoints  
# ================================

@router.get("/admin/audit/logs", dependencies=[Depends(check_rate_limit), Depends(verify_role(Role.ADMIN))])
async def query_audit_logs(
    event_type: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
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
        ) from e


@router.get("/admin/audit/stats", dependencies=[Depends(check_rate_limit), Depends(verify_role(Role.ADMIN))])
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
        ) from e


# ================================
# API Key Management Endpoints
# ================================

@router.post("/admin/api-keys/generate", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.ADMIN))])
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
            user_id=_short_id(target_user_id),
            status="success",
            details=f"New API key generated: {key_id}"
        )
        
        return {
            "status": "success",
            "message": "API key generated successfully",
            "api_key": new_key,
            "key_id": key_id,
            "user_id": _short_id(target_user_id),
            "expires_in_days": request.expiry_days,
            "warning": "Save this key securely. It will not be shown again."
        }

    except ValueError as e:
        # SECURITY: never echo internal exception text to the client
        logger.warning(f"API key generation rejected: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API key request"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate API key"
        ) from e


@router.post("/admin/api-keys/rotate", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
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
            user_id=_short_id(user_id),
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
        # SECURITY: never echo internal exception text to the client
        logger.warning(f"API key rotation rejected: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key rotation request"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rotate API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rotate API key"
        ) from e


@router.get("/admin/api-keys/list", dependencies=[Depends(check_rate_limit)])
async def list_api_keys(api_key: str = Depends(verify_api_key)):
    """List your API keys (shows metadata only, not the keys themselves)."""
    try:
        user_id = hash_api_key_for_logging(api_key)
        
        keys = api_key_manager.list_keys(user_id, active_only=False)
        active_keys = [k for k in keys if k["is_active"] and not k["is_expired"]]
        
        return {
            "status": "success",
            "user_id": _short_id(user_id),
            "total_keys": len(keys),
            "active_keys": len(active_keys),
            "keys": keys
        }
    
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys"
        ) from e


@router.delete("/admin/api-keys/revoke/{key_id}", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
async def revoke_api_key(key_id: str, api_key: str = Depends(verify_api_key)):
    """Revoke (deactivate) an API key by its ID.

    The caller may only revoke keys they own, unless they hold the ADMIN role.
    This prevents revoking another user's key by guessing its id (IDOR).
    """
    try:
        caller_user_id = hash_api_key_for_logging(api_key)
        owner_user_id = api_key_manager.get_key_owner(key_id)

        # Treat unknown keys as 404 without leaking ownership of others' keys.
        if owner_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )

        is_admin = rbac_manager.check_permission(caller_user_id, Role.ADMIN)
        if owner_user_id != caller_user_id and not is_admin:
            logger.warning("Denied cross-user API key revocation attempt")
            # Do not reveal that the key exists but belongs to someone else.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )

        success = api_key_manager.revoke_key(key_id)

        if success:
            user_id = caller_user_id
            
            # Log to audit
            audit_logger.log_security_event(
                event_subtype="api_key_revoked",
                user_id=_short_id(user_id),
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
        ) from e
