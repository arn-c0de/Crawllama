"""CSRF Protection Manager with Redis-backed token storage.

Provides Cross-Site Request Forgery (CSRF) protection for state-changing API operations.
Implements double-submit cookie pattern with server-side token validation.

Security Features:
- Cryptographically secure token generation (secrets module)
- Short-lived tokens (default 1 hour expiration)
- Per-session token binding
- Redis-backed distributed storage
- Origin and Referer header validation
- Protection for POST/PUT/PATCH/DELETE methods

Example Usage:
    csrf_manager = CSRFManager(redis_url="redis://localhost:6379/0")
    
    # Generate token for client
    token = csrf_manager.generate_token(user_id="user_123")
    
    # Validate token from client
    is_valid = csrf_manager.validate_token(user_id="user_123", token=token)
"""
import os
import time
import secrets
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

try:
    import redis
    from redis.connection import ConnectionPool
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from utils.logger import setup_logger

logger = setup_logger(__name__)


class CSRFManager:
    """CSRF token management with Redis storage."""
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        token_expiry: int = 3600,  # 1 hour default
        max_connections: int = 50,
        fallback_to_memory: bool = True
    ):
        """Initialize CSRF manager.
        
        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
            token_expiry: Token lifetime in seconds (default: 3600 = 1 hour)
            max_connections: Maximum Redis connection pool size
            fallback_to_memory: Use in-memory storage if Redis unavailable
        """
        self.token_expiry = token_expiry
        self.fallback_to_memory = fallback_to_memory
        self.memory_tokens: Dict[str, tuple[str, float]] = {}  # {user_id: (token, expiry)}
        self.using_redis = False  # Track actual backend in use
        
        # Initialize Redis connection
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
                pool = ConnectionPool.from_url(
                    redis_url,
                    max_connections=max_connections,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                self.redis_client = redis.Redis(connection_pool=pool)
                # Test connection
                self.redis_client.ping()
                self.using_redis = True
                logger.info(f"CSRF Manager: Redis connected at {redis_url}")
            except Exception as e:
                logger.warning(f"CSRF Manager: Redis connection failed: {e}")
                self.redis_client = None  # Clear redis client on failed connection
                if fallback_to_memory:
                    logger.info("CSRF Manager: Falling back to in-memory storage")
                else:
                    raise
        else:
            logger.warning("CSRF Manager: Redis library not available")
            if not fallback_to_memory:
                raise ImportError("Redis is required but not available")
            logger.info("CSRF Manager: Using in-memory storage")
    
    def generate_token(self, user_id: str) -> str:
        """Generate a new CSRF token for a user.
        
        Args:
            user_id: Unique identifier for the user (API key hash or session ID)
            
        Returns:
            A cryptographically secure CSRF token (44 characters, urlsafe)
        """
        # Generate 256-bit token (32 bytes = 44 chars in base64)
        token = secrets.token_urlsafe(32)
        expiry = time.time() + self.token_expiry
        
        # Store in Redis or memory
        if self.redis_client:
            try:
                key = f"csrf:{user_id}"
                # Store with automatic expiration
                self.redis_client.setex(
                    key,
                    self.token_expiry,
                    token
                )
                logger.debug(f"CSRF token generated and stored in Redis (expires in {self.token_expiry}s)")
                return token
            except Exception as e:
                logger.error(f"CSRF Manager: Redis storage failed: {e}")
                if self.fallback_to_memory:
                    logger.warning("CSRF Manager: Falling back to memory storage")
                else:
                    raise
        
        # Fallback to memory storage
        self.memory_tokens[user_id] = (token, expiry)
        logger.debug("CSRF token generated and stored in memory")
        return token
    
    def validate_token(self, user_id: str, token: str) -> bool:
        """Validate a CSRF token for a user.
        
        Args:
            user_id: Unique identifier for the user
            token: CSRF token to validate
            
        Returns:
            True if token is valid and not expired, False otherwise
        """
        if not token:
            logger.warning("CSRF validation failed: No token provided")
            return False
        
        # Check Redis storage
        if self.redis_client:
            try:
                key = f"csrf:{user_id}"
                stored_token = self.redis_client.get(key)
                
                if not stored_token:
                    logger.warning("CSRF validation failed: No token found in Redis")
                    return False
                
                # Constant-time comparison to prevent timing attacks
                is_valid = secrets.compare_digest(token, stored_token)
                if is_valid:
                    logger.debug("CSRF token validated successfully")
                else:
                    logger.warning("CSRF validation failed: Token mismatch")
                
                return is_valid
            except Exception as e:
                logger.error(f"CSRF Manager: Redis validation failed: {e}")
                if self.fallback_to_memory:
                    logger.warning("CSRF Manager: Falling back to memory validation")
                else:
                    return False
        
        # Fallback to memory storage
        if user_id not in self.memory_tokens:
            logger.warning("CSRF validation failed: No token in memory")
            return False
        
        stored_token, expiry = self.memory_tokens[user_id]
        
        # Check expiration
        if time.time() > expiry:
            logger.warning("CSRF validation failed: Token expired")
            del self.memory_tokens[user_id]
            return False
        
        # Constant-time comparison
        is_valid = secrets.compare_digest(token, stored_token)
        if is_valid:
            logger.debug("CSRF token validated successfully (memory)")
        else:
            logger.warning("CSRF validation failed: Token mismatch (memory)")
        
        return is_valid
    
    def revoke_token(self, user_id: str) -> bool:
        """Revoke (delete) a CSRF token for a user.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            True if token was revoked, False if no token existed
        """
        # Revoke from Redis
        if self.redis_client:
            try:
                key = f"csrf:{user_id}"
                result = self.redis_client.delete(key)
                if result > 0:
                    logger.debug(f"CSRF token revoked for user {user_id[:8]}...")
                    return True
            except Exception as e:
                logger.error(f"CSRF Manager: Redis revocation failed: {e}")
        
        # Revoke from memory
        if user_id in self.memory_tokens:
            del self.memory_tokens[user_id]
            logger.debug(f"CSRF token revoked (memory) for user {user_id[:8]}...")
            return True
        
        return False
    
    def cleanup_expired(self) -> int:
        """Clean up expired tokens from memory storage.
        
        Redis handles expiration automatically via TTL.
        This method only affects memory-backed storage.
        
        Returns:
            Number of expired tokens removed
        """
        current_time = time.time()
        expired_users = [
            user_id for user_id, (token, expiry) in self.memory_tokens.items()
            if expiry < current_time
        ]
        
        for user_id in expired_users:
            del self.memory_tokens[user_id]
        
        if expired_users:
            logger.info(f"CSRF Manager: Cleaned up {len(expired_users)} expired tokens from memory")
        
        return len(expired_users)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get CSRF manager statistics.
        
        Returns:
            Dictionary with token counts and configuration
        """
        stats = {
            "backend": "redis" if self.using_redis else "memory",
            "token_expiry_seconds": self.token_expiry,
            "memory_token_count": len(self.memory_tokens),
        }
        
        if self.redis_client and self.using_redis:
            try:
                # Count CSRF keys in Redis
                csrf_keys = self.redis_client.keys("csrf:*")
                stats["redis_token_count"] = len(csrf_keys)
            except Exception as e:
                logger.error(f"CSRF Manager: Failed to get Redis stats: {e}")
                stats["redis_error"] = str(e)
        
        return stats


# Global CSRF manager instance
_csrf_manager: Optional[CSRFManager] = None


def get_csrf_manager() -> CSRFManager:
    """Get the global CSRF manager instance.
    
    Initializes on first call with default configuration.
    """
    global _csrf_manager
    if _csrf_manager is None:
        _csrf_manager = CSRFManager()
    return _csrf_manager


def validate_origin_header(origin: Optional[str], allowed_origins: list[str]) -> bool:
    """Validate Origin header against allowed origins list.
    
    Args:
        origin: Origin header value from request
        allowed_origins: List of allowed origin URLs
        
    Returns:
        True if origin is valid, False otherwise
    """
    if not origin:
        return False
    
    # Normalize origin (remove trailing slash)
    origin = origin.rstrip("/")
    
    # Check against allowed list
    for allowed in allowed_origins:
        allowed = allowed.rstrip("/")
        if origin == allowed:
            return True
    
    return False


def validate_referer_header(referer: Optional[str], allowed_hosts: list[str]) -> bool:
    """Validate Referer header against allowed hosts list.
    
    Args:
        referer: Referer header value from request
        allowed_hosts: List of allowed hostnames
        
    Returns:
        True if referer is valid, False otherwise
    """
    if not referer:
        return False
    
    # Extract hostname from referer URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        referer_host = parsed.hostname
        
        if not referer_host:
            return False
        
        # Check against allowed hosts
        return referer_host in allowed_hosts
    except Exception as e:
        logger.warning(f"Failed to parse Referer header: {e}")
        return False
