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

# The SearchAgent keeps one conversation session (history, last search
# results, session.json) that is not thread-safe. API requests run in worker
# threads, so calls into it are serialized with this lock to keep concurrent
# requests from interleaving writes to that shared state.
agent_lock = threading.Lock()


def run_with_agent_lock(func, *args, **kwargs):
    """Call ``func`` while holding :data:`agent_lock` (use via asyncio.to_thread)."""
    with agent_lock:
        return func(*args, **kwargs)
