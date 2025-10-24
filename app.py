"""FastAPI application for CrawlLama - Production-ready API."""
import logging
from fastapi import FastAPI, HTTPException, Depends, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json
import time
from datetime import datetime
import asyncio

from core.agent import SearchAgent
from core.langgraph_agent import MultiHopReasoningAgent
from core.unified_loader import get_unified_loader
from core.health import get_system_monitor, get_performance_tracker, print_health_summary, shutdown_monitoring
from utils.secure_config import SecureConfig
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("crawllama")

# Initialize FastAPI app
app = FastAPI(
    title="CrawlLama API",
    description="AI-powered web research agent with multi-hop reasoning",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load configuration
try:
    config = json.load(open("config.json"))
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    config = {
        "llm": {"model": "qwen2.5:3b"},
        "cache": {"enabled": True}
    }

# Initialize components
agent = None
multihop_agent = None
system_monitor = None
performance_tracker = None


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global agent, multihop_agent, system_monitor, performance_tracker

    logger.info("Starting CrawlLama API...")

    # Initialize health monitoring
    system_monitor = get_system_monitor()
    performance_tracker = get_performance_tracker()
    logger.info("Health monitoring initialized")

    # Initialize standard agent
    agent = SearchAgent(config=config, enable_web=True, debug=False)
    logger.info("Standard agent initialized")

    # Initialize multi-hop agent
    multihop_agent = MultiHopReasoningAgent(
        config=config,
        max_hops=3,
        confidence_threshold=0.7
    )
    logger.info("Multi-hop agent initialized")

    logger.info("CrawlLama API started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down CrawlLama API...")

    # Print final health summary
    if system_monitor and performance_tracker:
        logger.info("Final health summary:")
        print_health_summary()

    # Shutdown monitoring
    shutdown_monitoring()


# Rate limiting (simple in-memory, use Redis for production)
request_counts: Dict[str, List[float]] = {}
RATE_LIMIT = 60  # requests per minute


def check_rate_limit(api_key: Optional[str] = Header(None)):
    """Simple rate limiting based on API key or IP."""
    key = api_key or "anonymous"
    current_time = time.time()

    if key not in request_counts:
        request_counts[key] = []

    # Remove old requests (older than 1 minute)
    request_counts[key] = [
        ts for ts in request_counts[key]
        if current_time - ts < 60
    ]

    if len(request_counts[key]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later."
        )

    request_counts[key].append(current_time)
    return key


# Request/Response models
class QueryRequest(BaseModel):
    """Query request model."""
    query: str = Field(..., description="Search query", min_length=1)
    use_multihop: bool = Field(False, description="Use multi-hop reasoning")
    max_hops: Optional[int] = Field(3, description="Maximum reasoning hops", ge=1, le=5)
    use_tools: bool = Field(True, description="Enable web search tools")
    stream: bool = Field(False, description="Stream response")


class QueryResponse(BaseModel):
    """Query response model."""
    answer: str
    confidence: Optional[float] = None
    steps: Optional[int] = None
    search_queries: Optional[List[str]] = None
    reasoning_path: Optional[List[str]] = None
    elapsed_time: float
    cached: bool = False


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str
    components: Dict[str, str]


class StatsResponse(BaseModel):
    """Statistics response."""
    agent_stats: Dict[str, Any]
    resource_stats: Dict[str, Any]
    uptime: float


# API Endpoints
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "CrawlLama API",
        "version": "1.0.0",
        "description": "AI-powered web research agent",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    components = {
        "agent": "healthy" if agent else "unavailable",
        "multihop_agent": "healthy" if multihop_agent else "unavailable",
        "system_monitor": "healthy" if system_monitor else "unavailable",
        "performance_tracker": "healthy" if performance_tracker else "unavailable"
    }

    return HealthResponse(
        status="healthy" if all(v == "healthy" for v in components.values()) else "degraded",
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        components=components
    )


@app.post("/query", response_model=QueryResponse, dependencies=[Depends(check_rate_limit)])
async def query_endpoint(request: QueryRequest):
    """
    Main query endpoint for processing search queries.

    Args:
        request: Query request with parameters

    Returns:
        Query response with answer and metadata
    """
    start_time = time.time()

    try:
        logger.info(f"Processing query: '{request.query}' (multihop={request.use_multihop})")

        if request.use_multihop:
            # Use multi-hop reasoning agent
            if not multihop_agent:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Multi-hop agent not available"
                )

            result = multihop_agent.query(request.query)

            return QueryResponse(
                answer=result["answer"],
                confidence=result.get("confidence"),
                steps=result.get("steps"),
                search_queries=result.get("search_queries"),
                reasoning_path=result.get("reasoning_path"),
                elapsed_time=time.time() - start_time,
                cached=False
            )

        else:
            # Use standard agent
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Agent not available"
                )

            answer = agent.query(request.query, use_tools=request.use_tools)

            return QueryResponse(
                answer=answer,
                elapsed_time=time.time() - start_time,
                cached=False
            )

    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )


@app.get("/stats", response_model=StatsResponse, dependencies=[Depends(check_rate_limit)])
async def stats_endpoint():
    """Get system statistics."""
    try:
        agent_stats = agent.get_stats() if agent else {}

        # Gather resource stats from health monitoring
        resource_stats = {}
        if system_monitor:
            metrics = system_monitor.get_latest_metrics()
            if metrics:
                resource_stats["system"] = {
                    "cpu_percent": metrics.cpu_percent,
                    "memory_percent": metrics.memory_percent,
                    "memory_used_gb": metrics.memory_used_gb,
                    "memory_total_gb": metrics.memory_total_gb,
                    "disk_percent": metrics.disk_percent,
                }

        if performance_tracker:
            perf_stats = performance_tracker.get_all_stats()
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
            uptime=time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0
        )

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@app.get("/plugins", dependencies=[Depends(check_rate_limit)])
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
        logger.error(f"Failed to list plugins: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list plugins"
        )


@app.post("/plugins/{plugin_name}/load", dependencies=[Depends(check_rate_limit)])
async def load_plugin(plugin_name: str):
    """Load a plugin dynamically."""
    try:
        loader = get_unified_loader()
        plugin = loader.load_plugin(plugin_name)

        return {
            "status": "loaded",
            "plugin": plugin_name,
            "message": f"Plugin '{plugin_name}' loaded successfully"
        }

    except Exception as e:
        logger.error(f"Failed to load plugin '{plugin_name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to load plugin: {str(e)}"
        )


@app.post("/plugins/{plugin_name}/unload", dependencies=[Depends(check_rate_limit)])
async def unload_plugin(plugin_name: str):
    """Unload a plugin."""
    try:
        loader = get_unified_loader()
        loader.unload_plugin(plugin_name)

        return {
            "status": "unloaded",
            "plugin": plugin_name,
            "message": f"Plugin '{plugin_name}' unloaded successfully"
        }

    except Exception as e:
        logger.error(f"Failed to unload plugin '{plugin_name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to unload plugin: {str(e)}"
        )


@app.get("/tools", dependencies=[Depends(check_rate_limit)])
async def list_tools():
    """List available tools."""
    try:
        loader = get_unified_loader()

        return {
            "loaded": loader.get_loaded_tools(),
            "available": list(loader._tool_configs.keys())
        }

    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tools"
        )


@app.post("/cache/clear", dependencies=[Depends(check_rate_limit)])
async def clear_cache():
    """Clear application cache."""
    try:
        if agent and agent.cache:
            agent.cache.clear_all()
            return {"status": "success", "message": "Cache cleared"}
        else:
            return {"status": "info", "message": "No cache to clear"}

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__
        }
    )


# Store startup time
@app.on_event("startup")
async def store_startup_time():
    """Store startup time for uptime calculation."""
    app.state.start_time = time.time()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
