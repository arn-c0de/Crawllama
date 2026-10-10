"""Memory-store endpoints (remember / recall / stats / forget)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api import runtime
from api.dependencies import (
    check_rate_limit,
    verify_csrf_token,
)
from api.models import ForgetRequest, MemoryRequest
from api.validation import validate_memory_category

logger = logging.getLogger("crawllama")

router = APIRouter()


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


@router.post("/memory/remember", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
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


@router.delete("/memory/forget", dependencies=[Depends(check_rate_limit), Depends(verify_csrf_token)])
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

