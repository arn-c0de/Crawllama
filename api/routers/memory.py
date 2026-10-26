"""Memory-store endpoints (remember / recall / stats / forget)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api import runtime
from api.dependencies import (
    check_rate_limit,
    verify_csrf_token,
    verify_role,
)
from api.models import ForgetRequest, MemoryRequest
from api.validation import validate_memory_category
from core.rbac_manager import Role

logger = logging.getLogger("crawllama")

router = APIRouter()

# Store method name patterns per singular category ("{}" is the category name)
_METHOD_PATTERNS = {
    'remember': 'remember_{}',
    'recall': 'get_all_{}s',
    'forget': 'forget_{}',
}
# Notes have their own "add" verb instead of remember_note()
_METHOD_OVERRIDES = {('remember', 'note'): 'add_note'}
_SINGULAR = {
    'email': 'email', 'emails': 'email',
    'phone': 'phone', 'phones': 'phone',
    'ip': 'ip', 'ips': 'ip',
    'username': 'username', 'usernames': 'username',
    'domain': 'domain', 'domains': 'domain',
    'note': 'note', 'notes': 'note',
}


def _store_method(action: str, category: str):
    """Resolve the memory-store method for an action on a category, or raise 400."""
    singular = _SINGULAR.get(category.lower())
    if singular is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported category for {action}: {category}"
        )
    name = _METHOD_OVERRIDES.get((action, singular), _METHOD_PATTERNS[action].format(singular))
    return getattr(runtime.memory_store, name)


@router.get("/memory", dependencies=[Depends(check_rate_limit)])
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


@router.post("/memory/remember", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.USER))])
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

        method = _store_method('remember', request.category)
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


@router.get("/memory/recall/{category}", dependencies=[Depends(check_rate_limit)])
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

        results = _store_method('recall', category)()

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


@router.get("/memory/stats", dependencies=[Depends(check_rate_limit)])
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


@router.delete("/memory/forget", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token), Depends(verify_role(Role.USER))])
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
            if not request.category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A category is required when forgetting a specific value"
                )
            success = _store_method('forget', request.category)(request.value)
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

