"""Mutable runtime singletons shared between app startup and the routers.

These are populated by ``app.startup_event`` and read by endpoints. Keeping
them on a dedicated module (rather than as ``app`` globals) lets the extracted
routers reach the same live objects without importing the app module. Tests
set the relevant attributes directly, e.g. ``runtime.agent = mock_agent``.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.agent import SearchAgent
    from core.langgraph_agent import MultiHopReasoningAgent
    from core.memory_store import MemoryStore
    from utils.redis_rate_limiter import RedisRateLimiter

# Application config (loaded by app.py) and the lock guarding config.json writes
config: dict[str, Any] = {}
config_loaded_from_file = False
config_lock = threading.Lock()

# Search / reasoning agents
agent: SearchAgent | None = None
multihop_agent: MultiHopReasoningAgent | None = None

# Persistence / intel memory
memory_store: MemoryStore | None = None

# Health monitoring
system_monitor: Any | None = None
performance_tracker: Any | None = None

# Redis-based rate limiter
redis_rate_limiter: RedisRateLimiter | None = None

# Adaptive hopping system
adaptive_manager: Any | None = None
adaptive_query_processor: Any | None = None

# The SearchAgent's conversation state is not thread-safe. API requests run
# in worker threads, so calls into the agent are serialized with this lock,
# and each principal's own session is swapped in for the call (see
# api.sessions) so clients never share history or search results.
agent_lock = threading.Lock()

# Per-principal sessions (set at startup; None -> the agent's own session)
sessions: Any | None = None


def run_with_agent_lock(func, *args, principal_id: str | None = None, **kwargs):
    """Call ``func`` under :data:`agent_lock` with the principal's session active.

    Use via ``asyncio.to_thread`` so the event loop is never blocked.
    """
    with agent_lock:
        if principal_id is None or sessions is None or agent is None:
            return func(*args, **kwargs)
        default_session = agent.session
        agent.session = sessions.get(principal_id)
        try:
            return func(*args, **kwargs)
        finally:
            agent.session = default_session
