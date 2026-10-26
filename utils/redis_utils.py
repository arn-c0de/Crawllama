"""Shared Redis connection setup for the security managers.

The API-key, RBAC and CSRF managers all need the same thing: a pooled,
decoding Redis client that is verified with ``ping()``, or ``None`` so the
caller can fall back to file/in-memory storage.
"""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit, urlunsplit

try:
    import redis
    from redis.connection import ConnectionPool
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from utils.logger import Logger

logger = Logger.get(__name__)

DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def redact_url_credentials(url: str) -> str:
    """Return URL with username/password removed from netloc for safe logging."""
    try:
        parsed = urlsplit(url)
        if "@" not in parsed.netloc:
            return url
        host_part = parsed.netloc.split("@", 1)[1]
        return urlunsplit((parsed.scheme, host_part, parsed.path, parsed.query, parsed.fragment))
    except Exception:
        return "redacted"


def connect_redis(
    component: str,
    redis_url: str | None = None,
    max_connections: int = 50,
    allow_fallback: bool = True,
    fallback_description: str = "in-memory storage",
) -> Any | None:
    """Create a pooled Redis client and verify it with ``ping()``.

    Args:
        component: Name used in log messages (e.g. "RBAC Manager")
        redis_url: Redis URL (default: ``REDIS_URL`` env or localhost)
        max_connections: Connection pool size
        allow_fallback: Return None instead of raising when Redis is unusable
        fallback_description: What the caller falls back to, for the log

    Returns:
        A connected ``redis.Redis`` client, or None when falling back.

    Raises:
        ImportError: Redis library missing and fallback not allowed
        Exception: Connection failure when fallback is not allowed
    """
    if not REDIS_AVAILABLE:
        logger.warning(f"{component}: Redis library not available")
        if not allow_fallback:
            raise ImportError("Redis is required but not available")
        logger.info(f"{component}: Using {fallback_description}")
        return None

    redis_url = redis_url or os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
    try:
        pool = ConnectionPool.from_url(
            redis_url,
            max_connections=max_connections,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        client = redis.Redis(connection_pool=pool)
        client.ping()
    except Exception as e:
        logger.warning(f"{component}: Redis connection failed: {e}")
        if not allow_fallback:
            raise
        logger.info(f"{component}: Falling back to {fallback_description}")
        return None

    logger.info(f"{component}: Redis connected at {redact_url_credentials(redis_url)}")
    return client
