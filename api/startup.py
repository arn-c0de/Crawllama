"""API startup/shutdown: config loading, security checks and component factories.

Every component factory falls back to ``None`` (degraded mode) on failure so
the API still starts with partial functionality.
"""
import json
import logging
import os
import time

from fastapi import FastAPI

from api import runtime
from api.security_config import (
    API_KEY,
    RATE_LIMIT_SECRET_EPHEMERAL,
    _is_loopback_host,
    hash_api_key_for_logging,
    is_dev_mode,
)
from api.sessions import PrincipalSessions
from core.agent import SearchAgent
from core.health import get_performance_tracker, get_system_monitor, print_health_summary, shutdown_monitoring
from core.langgraph_agent import MultiHopReasoningAgent, create_multihop_agent
from core.memory_store import MemoryStore, get_memory_store
from core.rbac_manager import Role, get_rbac_manager
from utils.redis_rate_limiter import RedisRateLimiter
from utils.tor_mode import TorError, initialize_tor_mode

logger = logging.getLogger("crawllama")


def load_app_config(path: str = "config.json") -> dict:
    """Load config.json into :mod:`api.runtime` (fallback skeleton if unreadable)."""
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
        runtime.config_loaded_from_file = True
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        config = {
            "llm": {"model": "qwen2.5:3b"},
            "cache": {"enabled": True}
        }
        # PATCH /config must never write this fallback skeleton over config.json
        runtime.config_loaded_from_file = False
    runtime.config = config
    return config


def validate_security_configuration():
    """Validate security configuration on startup.
    
    Checks for insecure configurations and logs warnings/errors.
    Only validates, does not block startup (except in strict mode).
    """
    issues = []
    warnings = []
    
    # Check if in DEV_MODE
    dev_mode = is_dev_mode()
    if dev_mode:
        warnings.append("⚠️  DEV_MODE is enabled - Security checks are relaxed")
    
    # Check API key configuration
    if not os.getenv("CRAWLLAMA_API_KEY"):
        if not dev_mode:
            warnings.append("⚠️  No CRAWLLAMA_API_KEY set - Using temporary key (insecure for production)")
    else:
        api_key = os.getenv("CRAWLLAMA_API_KEY")
        if len(api_key) < 32:
            issues.append("❌ CRAWLLAMA_API_KEY is too short (min 32 characters recommended)")
    
    # Check ALLOWED_HOSTS configuration
    if not os.getenv("ALLOWED_HOSTS"):
        warnings.append("⚠️  No ALLOWED_HOSTS set - Using defaults (configure for production)")
    
    # Check ALLOWED_ORIGINS configuration
    if not os.getenv("ALLOWED_ORIGINS"):
        warnings.append("⚠️  No ALLOWED_ORIGINS set - Using defaults (configure for production)")
    
    # Check RATE_LIMIT_SECRET
    if not os.getenv("RATE_LIMIT_SECRET"):
        warnings.append("⚠️  No RATE_LIMIT_SECRET set - Using temporary secret")
    
    # Check Redis configuration
    if not os.getenv("REDIS_URL"):
        warnings.append("ℹ️  No REDIS_URL set - Using in-memory fallbacks (not distributed)")
    
    # Log results
    if issues:
        logger.error("=" * 60)
        logger.error("🚨 SECURITY CONFIGURATION ISSUES 🚨")
        for issue in issues:
            logger.error(issue)
        logger.error("=" * 60)
    
    if warnings:
        logger.warning("=" * 60)
        logger.warning("🔒 SECURITY CONFIGURATION WARNINGS")
        for warning in warnings:
            logger.warning(warning)
        logger.warning("=" * 60)
    
    if not issues and not warnings:
        logger.info("✅ Security configuration validation passed")
    
    # In production strict mode, block startup on issues
    strict_mode = os.getenv("SECURITY_STRICT_MODE", "false").lower() == "true"
    if strict_mode and issues:
        logger.critical("SECURITY_STRICT_MODE enabled - Blocking startup due to security issues")
        raise RuntimeError("Security configuration validation failed in strict mode")
    
    return len(issues) == 0


def _enforce_dev_mode_loopback_only(dev_mode: bool) -> None:
    """Refuse to start in DEV_MODE when bound to a non-loopback address.

    SECURITY (fail closed): DEV_MODE disables API-key auth, CSRF and RBAC on
    EVERY endpoint (including /admin/* and /config). That is only acceptable on
    loopback. If the configured bind host is network-reachable, a single
    env-var misconfiguration would expose the entire unauthenticated admin
    surface — so refuse to start instead.
    """
    if not dev_mode:
        return
    host = (
        os.getenv("CRAWLLAMA_HOST")
        or os.getenv("HOST")
        or os.getenv("UVICORN_HOST")
        or "127.0.0.1"
    )
    if _is_loopback_host(host):
        return
    logger.critical(
        "CRAWLLAMA_DEV_MODE is enabled but the server is configured to bind a "
        f"non-loopback host ({host}). DEV_MODE disables authentication, CSRF and "
        "RBAC and must never be network-reachable. Refusing to start — unset "
        "CRAWLLAMA_DEV_MODE for production or bind to 127.0.0.1."
    )
    raise RuntimeError("DEV_MODE must not be bound to a non-loopback host")


def _enforce_persistent_rate_limit_secret(dev_mode: bool) -> None:
    """Refuse to start outside DEV_MODE without a persistent RATE_LIMIT_SECRET.

    SECURITY (fail closed): an ephemeral RATE_LIMIT_SECRET invalidates every
    issued managed-key hash on restart and yields non-portable rate-limit
    identities. Refuse to start in production without a persistent secret.
    """
    if RATE_LIMIT_SECRET_EPHEMERAL and not dev_mode:
        logger.critical(
            "RATE_LIMIT_SECRET is not set. Refusing to start outside DEV_MODE. "
            "Set RATE_LIMIT_SECRET in the environment for a persistent secret."
        )
        raise RuntimeError("RATE_LIMIT_SECRET is required outside DEV_MODE")


def _grant_bootstrap_admin_role() -> None:
    """Grant the bootstrap key administrative privileges.

    With the secure default role now READ_ONLY, the operator's bootstrap key
    must be explicitly elevated so that admin endpoints remain reachable out
    of the box.
    """
    try:
        bootstrap_user_id = hash_api_key_for_logging(API_KEY)
        get_rbac_manager().assign_role(bootstrap_user_id, Role.ADMIN, user_info="bootstrap")
        logger.info("Bootstrap API key granted ADMIN role")
    except Exception as e:
        logger.error(f"Failed to assign bootstrap admin role: {e}", exc_info=True)


def _create_redis_rate_limiter() -> RedisRateLimiter | None:
    """Initialize the Redis rate limiter; return None to fall back to in-memory limiting."""
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        limiter = RedisRateLimiter(redis_url=redis_url)
        logger.info(f"Redis rate limiter initialized: {redis_url}")
        return limiter
    except Exception as e:
        logger.warning(f"Failed to initialize Redis rate limiter: {e}")
        logger.warning("Falling back to in-memory rate limiting")
        return None


def _create_health_monitoring() -> tuple:
    """Initialize health monitoring; return (system_monitor, performance_tracker) or (None, None)."""
    try:
        monitor = get_system_monitor()
        tracker = get_performance_tracker()
        logger.info("Health monitoring initialized")
        return monitor, tracker
    except Exception as e:
        logger.error(f"Failed to initialize health monitoring: {e}", exc_info=True)
        # Continue without health monitoring
        return None, None


def _create_memory_store() -> MemoryStore | None:
    """Initialize the memory store; return None on failure."""
    try:
        # Use the process-wide singleton: a second instance would hold its own
        # copy of memory.json and overwrite the agent's changes (and vice versa)
        store = get_memory_store()
        logger.info("Memory store initialized")
        return store
    except Exception as e:
        logger.error(f"Failed to initialize memory store: {e}", exc_info=True)
        # Continue without memory store
        return None


def _create_standard_agent() -> SearchAgent | None:
    """Initialize the standard search agent; return None on failure."""
    try:
        search_agent = SearchAgent(config=runtime.config, enable_web=True, debug=False)
        logger.info("Standard agent initialized")
        return search_agent
    except Exception as e:
        logger.error(f"Failed to initialize standard agent: {e}", exc_info=True)
        # Continue without standard agent
        return None


def _create_multihop_agent() -> MultiHopReasoningAgent | None:
    """Initialize the multi-hop reasoning agent; return None on failure."""
    try:
        reasoning_agent = create_multihop_agent(runtime.config)
        logger.info("Multi-hop agent initialized")
        return reasoning_agent
    except Exception as e:
        logger.error(f"Failed to initialize multi-hop agent: {e}", exc_info=True)
        # Continue without multi-hop agent
        return None


def _create_adaptive_system(search_agent, reasoning_agent, monitor, tracker) -> tuple:
    """Initialize the Adaptive Hopping System; return (manager, processor) or (None, None)."""
    try:
        from core.adaptive_integration import initialize_adaptive_system
        from core.cloud_llm_client import create_llm_client_from_config

        # LLM client for complexity detection - provider-aware, so cloud
        # configs get working adaptive features too (previously Ollama-only).
        llm = create_llm_client_from_config(runtime.config.get("llm", {}))

        manager, processor = initialize_adaptive_system(
            llm=llm,
            agent=search_agent,
            multihop_agent=reasoning_agent,
            system_monitor=monitor,
            performance_tracker=tracker
        )
        logger.info("Adaptive Hopping System initialized")
        return manager, processor
    except Exception as e:
        logger.error(f"Failed to initialize Adaptive Hopping System: {e}", exc_info=True)
        logger.warning("API will continue without adaptive features")
        return None, None


async def startup_event(app: FastAPI):
    """Initialize components on startup."""

    logger.info("Starting CrawlLama API...")

    # Tor mode must be active (and verified) before any component can make a
    # web request; an unreachable Tor network aborts startup (fail fast).
    try:
        tor_config = initialize_tor_mode(runtime.config)
    except TorError as e:
        logger.critical(f"Startup aborted: {e}")
        raise
    if tor_config.enabled:
        logger.info(f"Tor mode active: all web traffic routed via {tor_config.proxy_url}")

    dev_mode = is_dev_mode()

    _enforce_dev_mode_loopback_only(dev_mode)
    _enforce_persistent_rate_limit_secret(dev_mode)

    # Validate security configuration FIRST
    try:
        validate_security_configuration()
    except RuntimeError as e:
        logger.critical(f"Startup aborted: {e}")
        raise

    if not dev_mode:
        _grant_bootstrap_admin_role()

    # Store startup time for uptime calculation
    app.state.start_time = time.time()

    # Initialize components (each falls back to None/degraded mode on failure)
    runtime.redis_rate_limiter = _create_redis_rate_limiter()
    runtime.system_monitor, runtime.performance_tracker = _create_health_monitoring()
    runtime.memory_store = _create_memory_store()
    runtime.agent = _create_standard_agent()
    # One conversation session per principal (API clients never share history)
    runtime.sessions = PrincipalSessions(
        base_dir=runtime.config.get("paths", {}).get("sessions_dir", "data/sessions")
    )
    runtime.multihop_agent = _create_multihop_agent()

    # Check if critical components are initialized
    if not runtime.agent and not runtime.multihop_agent:
        logger.warning("WARNING: No agents initialized! API will have limited functionality.")

    runtime.adaptive_manager, runtime.adaptive_query_processor = _create_adaptive_system(
        runtime.agent, runtime.multihop_agent, runtime.system_monitor, runtime.performance_tracker
    )

    logger.info("CrawlLama API started successfully")


async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down CrawlLama API...")

    # Close Redis connection
    if runtime.redis_rate_limiter:
        try:
            runtime.redis_rate_limiter.close()
            logger.info("Redis rate limiter closed")
        except Exception as e:
            logger.error(f"Error closing Redis rate limiter: {e}")

    # Print final health summary
    if runtime.system_monitor and runtime.performance_tracker:
        logger.info("Final health summary:")
        print_health_summary()

    # Shutdown monitoring
    shutdown_monitoring()

    logger.info("CrawlLama API shutdown complete")
