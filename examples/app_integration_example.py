"""
Example integration code for adding Adaptive Hops to app.py

This file shows the exact code changes needed to integrate
the adaptive system into the main CrawlLama API.

Copy the relevant sections into your app.py file.

Author: CrawlLama Team
"""

# ============================================================================
# STEP 1: Add imports (around line 23, after existing imports)
# ============================================================================

from core.adaptive_integration import initialize_adaptive_system

# ============================================================================
# STEP 2: Initialize adaptive system (around line 295, after multihop_agent)
# ============================================================================

# Initialize adaptive system
adaptive_manager = None
adaptive_processor = None

try:
    adaptive_manager, adaptive_processor = initialize_adaptive_system(
        llm=agent.llm,  # Reuse LLM from SearchAgent
        agent=agent,
        multihop_agent=multihop_agent,
        system_monitor=system_monitor,
        performance_tracker=performance_tracker
    )
    logger.info("Adaptive system initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize adaptive system: {e}", exc_info=True)
    # Continue without adaptive system

# ============================================================================
# STEP 3: Add Pydantic models (around line 550, after existing models)
# ============================================================================

class AdaptiveQueryRequest(BaseModel):
    """Request model for adaptive query endpoint."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUERY_LENGTH,
        description="User query"
    )
    force_complexity: Optional[str] = Field(
        None,
        description="Force specific complexity: 'low', 'mid', or 'high'"
    )
    enable_escalation: bool = Field(
        True,
        description="Enable confidence-based escalation"
    )

    @validator('query')
    def sanitize_query_input(cls, v):
        return sanitize_query(v)


class AdaptiveQueryResponse(BaseModel):
    """Response model for adaptive query endpoint."""
    answer: str
    confidence: Optional[float]
    strategy: Dict[str, Any]
    metadata: Dict[str, Any]
    steps: Optional[int] = None
    search_queries: Optional[List[str]] = None
    reasoning_path: Optional[List[str]] = None

# ============================================================================
# STEP 4: Add adaptive endpoint (around line 768, after /query endpoint)
# ============================================================================

@app.post(
    "/query-adaptive",
    response_model=AdaptiveQueryResponse,
    dependencies=[Depends(check_rate_limit)]
)
async def query_adaptive_endpoint(request: AdaptiveQueryRequest):
    """
    Adaptive query endpoint with automatic agent selection.

    This endpoint automatically selects the optimal agent based on:
    - Query complexity analysis
    - System resource constraints
    - Confidence-based escalation

    Args:
        request: Adaptive query request with query and options

    Returns:
        Response with answer, strategy, and detailed metadata

    Example:
        POST /query-adaptive
        {
            "query": "Compare AI in healthcare vs manufacturing",
            "enable_escalation": true
        }

        Response:
        {
            "answer": "...",
            "confidence": 0.85,
            "strategy": {
                "complexity": "high",
                "agent_type": "MultiHopReasoningAgent",
                "max_hops": 5,
                "reasoning": ["High complexity: MultiHop with 5 hops"]
            },
            "metadata": {
                "attempts": 1,
                "elapsed_time": 12.5,
                "escalation_history": []
            }
        }
    """
    if not adaptive_processor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adaptive system not available"
        )

    try:
        logger.info(f"Adaptive query: '{request.query}' (force={request.force_complexity}, escalation={request.enable_escalation})")

        result = adaptive_processor.process_query(
            query=request.query,
            force_complexity=request.force_complexity,
            enable_escalation=request.enable_escalation
        )

        return AdaptiveQueryResponse(**result)

    except Exception as e:
        logger.error(f"Adaptive query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Adaptive query processing failed. Please check your input and try again."
        )

# ============================================================================
# STEP 5 (Optional): Extend /stats endpoint (around line 788)
# ============================================================================

@app.get("/stats", response_model=StatsResponse, dependencies=[Depends(check_rate_limit)])
async def stats_endpoint():
    """Get system statistics."""
    try:
        agent_stats = agent.get_stats() if agent else {}

        # ... existing code ...

        # Add adaptive system stats
        adaptive_stats = {}
        if adaptive_manager:
            try:
                adaptive_stats = adaptive_manager.get_stats()
            except Exception as e:
                logger.warning(f"Failed to get adaptive stats: {e}")

        return StatsResponse(
            total_queries=agent_stats.get("total_queries", 0),
            cache_hits=agent_stats.get("cache_hits", 0),
            avg_response_time=agent_stats.get("avg_response_time", 0),
            resources=resource_stats,
            adaptive=adaptive_stats  # Add this field
        )

    except Exception as e:
        logger.error(f"Failed to fetch stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch statistics"
        )

# ============================================================================
# COMPLETE INTEGRATION CHECKLIST
# ============================================================================

"""
✓ Step 1: Import adaptive_integration module
✓ Step 2: Initialize adaptive_manager and adaptive_processor
✓ Step 3: Add AdaptiveQueryRequest and AdaptiveQueryResponse models
✓ Step 4: Add /query-adaptive endpoint
✓ Step 5: (Optional) Add adaptive stats to /stats endpoint

After integration:
1. Restart the CrawlLama API server
2. Test with: POST /query-adaptive
3. Check logs for: "Adaptive system initialized successfully"
4. Monitor adaptive decisions in logs

Example curl command:
```bash
curl -X POST "http://localhost:8000/query-adaptive" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare supervised and unsupervised learning",
    "enable_escalation": true
  }'
```

For detailed documentation, see: ADAPTIVE_HOPS.md
"""

# ============================================================================
# CONFIGURATION OPTIONS
# ============================================================================

"""
You can customize the adaptive system by modifying initialize_adaptive_system():

from core.adaptive_hops import AdaptiveConfig

custom_config = AdaptiveConfig(
    # Feature toggles
    enable_resource_monitoring=True,
    enable_confidence_escalation=True,

    # Resource thresholds
    cpu_threshold_high=70.0,  # Lower for more aggressive degradation
    memory_threshold_high=80.0,

    # Confidence thresholds
    confidence_low=0.6,  # Higher for stricter escalation
    confidence_medium=0.75,
    confidence_high=0.9,

    # Hops per complexity
    max_hops_low=0,
    max_hops_mid=1,
    max_hops_high=3,  # Reduce for faster responses

    # Fallback
    fallback_on_resource_constraint=True,
    degraded_mode_max_hops=1
)

# Then pass config to AdaptiveHopManager in initialize_adaptive_system()
"""
