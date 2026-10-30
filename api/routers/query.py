"""Query endpoints: standard, multi-hop and adaptive answering."""
import asyncio
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status

from api import runtime
from api.dependencies import check_rate_limit, get_principal_id
from api.models import AdaptiveQueryRequest, AdaptiveQueryResponse, QueryRequest, QueryResponse
from core.agent.constants import is_result_reference
from core.langgraph_agent import DEFAULT_CONFIDENCE_THRESHOLD, DEFAULT_MAX_HOPS, MultiHopReasoningAgent
from utils.validators import sanitize_exception_message

logger = logging.getLogger("crawllama")

router = APIRouter()


async def _run_multihop_query(request: QueryRequest, start_time: float) -> QueryResponse:
    """Answer a query with the multi-hop reasoning agent."""
    if not runtime.multihop_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Multi-hop agent not available"
        )

    # Use custom max_hops if provided (pydantic guarantees 1 <= max_hops <= 5)
    if request.max_hops and request.max_hops != DEFAULT_MAX_HOPS:
        reasoning_agent = MultiHopReasoningAgent(
            config=runtime.config,
            max_hops=request.max_hops,
            confidence_threshold=DEFAULT_CONFIDENCE_THRESHOLD
        )
    else:
        reasoning_agent = runtime.multihop_agent

    # Offload the blocking (sync HTTP + LLM) work to a worker thread
    # so it does not stall the event loop and kill concurrency.
    result = await asyncio.to_thread(reasoning_agent.query, request.query)

    return QueryResponse(
        answer=result["answer"],
        confidence=result.get("confidence"),
        steps=result.get("steps"),
        search_queries=result.get("search_queries"),
        reasoning_path=result.get("reasoning_path"),
        elapsed_time=time.time() - start_time,
        cached=False
    )


async def _run_standard_query(request: QueryRequest, start_time: float, principal_id: str) -> QueryResponse:
    """Answer a query with the standard search agent."""
    if not runtime.agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not available"
        )

    answer = await asyncio.to_thread(
        runtime.run_with_agent_lock, runtime.agent.query, request.query,
        use_tools=request.use_tools, principal_id=principal_id,
    )

    return QueryResponse(
        answer=answer,
        elapsed_time=time.time() - start_time,
        cached=False
    )


@router.post("/query", response_model=QueryResponse, dependencies=[Depends(check_rate_limit)])
async def query_endpoint(request: QueryRequest, principal_id: str = Depends(get_principal_id)):
    """
    Main query endpoint for processing search queries.

    Args:
        request: Query request with parameters

    Returns:
        Query response with answer and metadata
    """
    start_time = time.time()

    try:
        logger.info("Processing query: '%s' (multihop=%s)", request.query, request.use_multihop)  # lgtm[py/log-injection] - parameterized logging; false positive

        # BUGFIX: Check if query is a result reference or uses < prefix
        # These should ALWAYS use SearchAgent, never MultiHopReasoningAgent
        is_context_mode = request.query.strip().startswith('<')
        is_result_ref = is_result_reference(request.query)

        # Force SearchAgent for result references and context-only mode
        use_multihop = request.use_multihop and not is_context_mode and not is_result_ref

        if is_context_mode or is_result_ref:
            logger.info(f"Forcing SearchAgent (context_mode={is_context_mode}, result_ref={is_result_ref})")

        if use_multihop:
            return await _run_multihop_query(request, start_time)
        return await _run_standard_query(request, start_time, principal_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query processing failed. Please check your input and try again."
        ) from e


@router.post("/query-adaptive", response_model=AdaptiveQueryResponse, dependencies=[Depends(check_rate_limit)])
async def adaptive_query_endpoint(
    request: AdaptiveQueryRequest, principal_id: str = Depends(get_principal_id)
):
    """
    Adaptive query endpoint with intelligent agent selection.

    Uses the Adaptive Hopping System to automatically select the best agent
    (SearchAgent or MultiHopReasoningAgent) based on query complexity.

    Features:
    - Automatic complexity detection (LOW/MID/HIGH)
    - Confidence-based escalation
    - Resource-aware degradation
    - Force complexity override
    - Detailed strategy metadata

    Args:
        request: Adaptive query request with parameters

    Returns:
        Adaptive query response with answer, strategy, and metadata
    """
    try:
        logger.info(
            "Processing adaptive query: '%s' (force_complexity=%s, enable_escalation=%s)",
            request.query,
            request.force_complexity,
            request.enable_escalation
        )  # lgtm[py/log-injection] - parameterized logging; false positive

        if not runtime.adaptive_query_processor:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Adaptive Hopping System not available. Please check system configuration."
            )

        # Process query with adaptive system (offloaded; it performs blocking
        # sync HTTP + LLM work that must not stall the event loop).
        result = await asyncio.to_thread(
            runtime.run_with_agent_lock,
            runtime.adaptive_query_processor.process_query,
            query=request.query,
            force_complexity=request.force_complexity,
            enable_escalation=request.enable_escalation,
            principal_id=principal_id,
        )

        logger.info(
            f"Adaptive query completed | "
            f"Complexity: {result['strategy']['complexity']} | "
            f"Agent: {result['strategy']['agent_type']} | "
            f"Attempts: {result['metadata']['attempts']} | "
            f"Time: {result['metadata']['elapsed_time']:.2f}s"
        )

        return AdaptiveQueryResponse(
            answer=result["answer"],
            confidence=result.get("confidence"),
            strategy=result["strategy"],
            metadata=result["metadata"],
            steps=result.get("steps"),
            search_queries=result.get("search_queries"),
            reasoning_path=result.get("reasoning_path")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Adaptive query processing failed: {sanitize_exception_message(str(e))}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Adaptive query processing failed"
        ) from e


@router.get("/context/status", dependencies=[Depends(check_rate_limit)])
async def context_status():
    """Get context usage status."""
    try:
        if runtime.agent and hasattr(runtime.agent, 'context_manager'):
            context_mgr = runtime.agent.context_manager
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
        ) from e
