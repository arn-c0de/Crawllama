"""Redis-based distributed rate limiting with Token Bucket algorithm.

Provides DoS protection through distributed rate limiting across multiple servers.
Implements Token Bucket algorithm for flexible rate limiting with burst support.

Security Features:
- Per-user rate limiting (prevents single user from overwhelming system)
- Per-endpoint rate limiting (different limits for different operations)
- Distributed across multiple API servers (Redis central store)
- Sliding window tracking (accurate rate calculation)
- Connection pooling (efficient Redis connections)
- Automatic key expiration (memory efficient)

Example Configuration:
    REDIS_URL = "redis://localhost:6379/0"
    
    rate_limiter = RedisRateLimiter(redis_url=REDIS_URL)
    
    # Check if request is allowed
    allowed = rate_limiter.check_rate_limit(
        user_id="user_123",
        endpoint="/query",
        limit=10,      # 10 requests
        window=60      # per 60 seconds
    )
"""
import os
import time
import logging
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, Callable
from datetime import datetime

try:
    import redis
    from redis.connection import ConnectionPool
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class _BucketState:
    """Token-bucket state threaded through a single rate-limit check."""
    key: str
    user_id: str
    endpoint: str
    limit: int
    window: int
    current_time: float
    tokens: float = 0.0
    refill_rate: float = 0.0


class RedisRateLimiter:
    """Redis-based distributed rate limiter using Token Bucket algorithm."""
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        redis_client: Optional[Any] = None,
        max_connections: int = 50,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5,
        retry_on_timeout: bool = True,
        time_source: Optional[Callable[[], float]] = None
    ):
        """
        Initialize Redis rate limiter.

        Args:
            redis_url: Redis connection URL (redis://host:port/db)
            redis_client: Existing Redis client (for testing/injection)
            max_connections: Maximum connections in pool
            socket_timeout: Socket timeout in seconds
            socket_connect_timeout: Connection timeout in seconds
            retry_on_timeout: Retry on timeout
            time_source: Clock used for token-bucket math (defaults to
                time.time). Injectable so tests can use a deterministic clock
                instead of the wall clock, which otherwise makes the
                time-based tests flaky under load.

        Raises:
            ImportError: If redis package not installed
            redis.ConnectionError: If cannot connect to Redis
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "Redis package not installed. Install with: pip install redis"
            )

        self._now = time_source or time.time

        # Process-local token buckets used as a fail-CLOSED fallback when Redis
        # is unavailable. This keeps rate limiting active (per-process) instead
        # of disabling it entirely, which would turn a Redis outage into a DoS
        # amplifier. {key: (tokens, last_update)}
        self._memory_buckets: Dict[str, Tuple[float, float]] = {}
        self._memory_lock = threading.Lock()

        # Use injected client (for testing) or create new connection
        if redis_client:
            self.redis = redis_client
            self.connection_pool = None
            logger.info("Using injected Redis client")
        else:
            # Get Redis URL from env or parameter
            redis_url = redis_url or os.getenv(
                "REDIS_URL",
                "redis://localhost:6379/0"
            )
            
            # Create connection pool for efficiency
            self.connection_pool = ConnectionPool.from_url(
                redis_url,
                max_connections=max_connections,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                retry_on_timeout=retry_on_timeout,
                decode_responses=True  # Auto-decode bytes to str
            )
            
            # Create Redis client from pool
            self.redis = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connection
            try:
                self.redis.ping()
                logger.info(f"Connected to Redis: {redis_url}")
            except redis.ConnectionError as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    def _get_key(self, user_id: str, endpoint: str) -> str:
        """
        Generate Redis key for rate limiting.
        
        Args:
            user_id: User identifier (API key hash, IP, etc.)
            endpoint: API endpoint path
            
        Returns:
            Redis key string
        """
        # Sanitize inputs to prevent key injection
        user_id_safe = user_id.replace(":", "_").replace(" ", "_")
        endpoint_safe = endpoint.replace(":", "_").replace(" ", "_").replace("/", "_")
        
        return f"ratelimit:{user_id_safe}:{endpoint_safe}"
    
    def check_rate_limit(
        self,
        user_id: str,
        endpoint: str,
        limit: int,
        window: int
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit using Token Bucket algorithm.
        
        Token Bucket Algorithm:
        1. Each user has a bucket with `limit` tokens
        2. Tokens refill at rate of `limit/window` per second
        3. Each request consumes 1 token
        4. Request allowed if token available, denied otherwise
        
        Args:
            user_id: User identifier (API key hash, IP, username)
            endpoint: API endpoint path (e.g., "/query", "/search")
            limit: Maximum requests allowed in window
            window: Time window in seconds
            
        Returns:
            Tuple of (allowed, info_dict):
                - allowed: True if request allowed, False if rate limit exceeded
                - info_dict: {
                    "remaining": remaining requests,
                    "reset_at": Unix timestamp when limit resets,
                    "retry_after": seconds to wait before retry
                  }
        """
        key = self._get_key(user_id, endpoint)
        current_time = self._now()
        state = _BucketState(
            key=key, user_id=user_id, endpoint=endpoint,
            limit=limit, window=window, current_time=current_time,
        )

        try:
            tokens, last_update = self._read_bucket_state(key, limit, current_time)
            state.tokens, state.refill_rate = self._refill_bucket(
                tokens, last_update, current_time, limit, window
            )

            if state.tokens >= 1.0:
                return self._consume_token(state)
            return self._reject_request(state)

        except (redis.RedisError, Exception) as e:
            logger.error(f"Redis error in rate limiting: {e}")
            # SECURITY: fail closed onto a process-local token bucket rather than
            # allowing unconditionally. A Redis outage must not disable rate
            # limiting (which would amplify a DoS).
            return self._check_rate_limit_memory(key, limit, window, current_time)

    def _read_bucket_state(
        self, key: str, limit: int, current_time: float
    ) -> Tuple[float, float]:
        """Read (tokens, last_update) from Redis, initializing on first request."""
        pipe = self.redis.pipeline()
        pipe.get(f"{key}:tokens")      # Current token count
        pipe.get(f"{key}:last_update") # Last update timestamp
        tokens_str, last_update_str = pipe.execute()

        # Initialize bucket if first request
        if tokens_str is None or last_update_str is None:
            return float(limit), current_time
        return float(tokens_str), float(last_update_str)

    @staticmethod
    def _refill_bucket(
        tokens: float, last_update: float, current_time: float, limit: int, window: int
    ) -> Tuple[float, float]:
        """Refill tokens based on elapsed time; return (tokens, refill_rate)."""
        # Handle zero limit edge case
        if limit == 0:
            return 0.0, 0.0

        elapsed = current_time - last_update
        refill_rate = limit / window  # tokens per second
        # Add tokens (up to limit)
        return min(limit, tokens + elapsed * refill_rate), refill_rate

    def _consume_token(self, state: _BucketState) -> Tuple[bool, Dict[str, Any]]:
        """Consume one token, persist the new bucket state, and allow the request."""
        tokens = state.tokens - 1.0

        # Update Redis with new state
        pipe = self.redis.pipeline()
        pipe.set(f"{state.key}:tokens", tokens, ex=state.window * 2)
        pipe.set(f"{state.key}:last_update", state.current_time, ex=state.window * 2)
        pipe.execute()

        remaining = int(tokens)
        reset_at = state.current_time + ((state.limit - tokens) / state.refill_rate)

        logger.debug(
            f"Rate limit OK for {state.user_id} on {state.endpoint}: "
            f"{remaining}/{state.limit} remaining"
        )

        return True, {
            "remaining": remaining,
            "reset_at": int(reset_at),
            "retry_after": 0
        }

    @staticmethod
    def _reject_request(state: _BucketState) -> Tuple[bool, Dict[str, Any]]:
        """Deny the request and report when the next token becomes available."""
        if state.refill_rate > 0:
            time_to_next_token = (1.0 - state.tokens) / state.refill_rate
            reset_at = state.current_time + time_to_next_token
            retry_after = int(time_to_next_token) + 1
        else:
            # Zero refill rate (limit=0) - never allowed
            reset_at = state.current_time + state.window
            retry_after = state.window

        logger.warning(
            f"Rate limit EXCEEDED for {state.user_id} on {state.endpoint}: "
            f"0/{state.limit} remaining, retry after {retry_after}s"
        )

        return False, {
            "remaining": 0,
            "reset_at": int(reset_at),
            "retry_after": retry_after
        }

    def _check_rate_limit_memory(
        self, key: str, limit: int, window: int, current_time: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """Process-local token-bucket fallback used when Redis is unavailable."""
        with self._memory_lock:
            tokens, last_update = self._memory_buckets.get(
                key, (float(limit), current_time)
            )

            if limit <= 0:
                tokens, refill_rate = 0.0, 0.0
            else:
                refill_rate = limit / window
                tokens = min(float(limit), tokens + (current_time - last_update) * refill_rate)

            if tokens >= 1.0:
                tokens -= 1.0
                self._memory_buckets[key] = (tokens, current_time)
                return True, {
                    "remaining": int(tokens),
                    "reset_at": int(current_time + window),
                    "retry_after": 0,
                    "degraded": "in-memory fallback (Redis unavailable)",
                }

            self._memory_buckets[key] = (tokens, current_time)
            retry_after = int((1.0 - tokens) / refill_rate) + 1 if refill_rate > 0 else window
            return False, {
                "remaining": 0,
                "reset_at": int(current_time + retry_after),
                "retry_after": retry_after,
                "degraded": "in-memory fallback (Redis unavailable)",
            }
    
    def reset_rate_limit(self, user_id: str, endpoint: str) -> bool:
        """
        Reset rate limit for specific user/endpoint.
        
        Args:
            user_id: User identifier
            endpoint: API endpoint path
            
        Returns:
            True if reset successful, False otherwise
        """
        key = self._get_key(user_id, endpoint)
        
        try:
            pipe = self.redis.pipeline()
            pipe.delete(f"{key}:tokens")
            pipe.delete(f"{key}:last_update")
            results = pipe.execute()
            
            deleted = sum(results)
            logger.info(f"Reset rate limit for {user_id} on {endpoint}")
            return deleted > 0
            
        except redis.RedisError as e:
            logger.error(f"Failed to reset rate limit: {e}")
            return False
    
    def get_rate_limit_status(
        self,
        user_id: str,
        endpoint: str,
        limit: int,
        window: int
    ) -> Dict[str, Any]:
        """
        Get current rate limit status without consuming a token.
        
        Args:
            user_id: User identifier
            endpoint: API endpoint path
            limit: Maximum requests allowed
            window: Time window in seconds
            
        Returns:
            Status dict with tokens, remaining, reset_at
        """
        key = self._get_key(user_id, endpoint)
        current_time = self._now()
        
        try:
            pipe = self.redis.pipeline()
            pipe.get(f"{key}:tokens")
            pipe.get(f"{key}:last_update")
            results = pipe.execute()
            
            tokens_str = results[0]
            last_update_str = results[1]
            
            if tokens_str is None:
                # No data - full bucket
                return {
                    "tokens": float(limit),
                    "remaining": limit,
                    "reset_at": int(current_time + window),
                    "limit": limit,
                    "window": window
                }
            
            tokens = float(tokens_str)
            last_update = float(last_update_str)
            
            # Calculate current tokens (with refill)
            elapsed = current_time - last_update
            refill_rate = limit / window
            current_tokens = min(limit, tokens + (elapsed * refill_rate))
            
            return {
                "tokens": current_tokens,
                "remaining": int(current_tokens),
                "reset_at": int(current_time + ((limit - current_tokens) / refill_rate)),
                "limit": limit,
                "window": window
            }
            
        except redis.RedisError as e:
            logger.error(f"Failed to get rate limit status: {e}")
            return {
                "tokens": 0,
                "remaining": 0,
                "reset_at": 0,
                "limit": limit,
                "window": window,
                "error": str(e)
            }
    
    def cleanup_expired_keys(self, pattern: str = "ratelimit:*") -> int:
        """
        Cleanup expired rate limit keys (maintenance operation).
        
        Args:
            pattern: Redis key pattern to match
            
        Returns:
            Number of keys deleted
        """
        try:
            deleted = 0
            cursor = 0
            
            while True:
                cursor, keys = self.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    # Delete keys in batch
                    deleted += self.redis.delete(*keys)
                
                if cursor == 0:
                    break
            
            logger.info(f"Cleaned up {deleted} expired rate limit keys")
            return deleted
            
        except redis.RedisError as e:
            logger.error(f"Failed to cleanup keys: {e}")
            return 0
    
    def close(self):
        """Close Redis connection and cleanup resources."""
        try:
            if self.connection_pool:
                self.connection_pool.disconnect()
                logger.info("Redis connection pool closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


# Default rate limits per endpoint
DEFAULT_RATE_LIMITS = {
    "/query": {"limit": 10, "window": 60},      # 10 requests per minute
    "/osint/query": {"limit": 5, "window": 60}, # 5 OSINT queries per minute
    "/osint/company": {"limit": 5, "window": 60}, # 5 company OSINT queries per minute
    "/search": {"limit": 20, "window": 60},     # 20 searches per minute
    "/memory/remember": {"limit": 30, "window": 60},  # 30 memory operations per minute
    "default": {"limit": 60, "window": 60}      # 60 requests per minute default
}


def get_rate_limit_for_endpoint(endpoint: str) -> tuple[int, int]:
    """
    Get rate limit configuration for endpoint.
    
    Args:
        endpoint: API endpoint path
        
    Returns:
        Tuple of (limit, window) in (requests, seconds)
    """
    # Match exact endpoint or use default
    config = DEFAULT_RATE_LIMITS.get(endpoint, DEFAULT_RATE_LIMITS["default"])
    return config["limit"], config["window"]
