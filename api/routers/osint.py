"""OSINT query endpoints (operator queries and company investigation)."""
import asyncio
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status

from api import runtime
from api.dependencies import check_rate_limit
from api.models import CompanyOSINTRequest, OSINTRequest
from utils.validators import sanitize_exception_message

logger = logging.getLogger("crawllama")

router = APIRouter()


@router.post("/osint/query", dependencies=[Depends(check_rate_limit)])
async def osint_query(request: OSINTRequest):
    """Execute OSINT query with operators."""
    try:
        if not runtime.agent:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Agent not available"
            )

        start_time = time.time()
        answer = await asyncio.to_thread(runtime.run_with_agent_lock, runtime.agent.query, request.query, use_tools=True)

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
        ) from e


@router.post("/osint/company", dependencies=[Depends(check_rate_limit)])
async def osint_company(request: CompanyOSINTRequest):
    """Execute company-focused OSINT query using natural input."""
    try:
        if not runtime.agent:
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
        answer = await asyncio.to_thread(runtime.run_with_agent_lock, runtime.agent.query, synthesized_query, use_tools=True)

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
        ) from e
