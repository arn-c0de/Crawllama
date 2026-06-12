"""Role-Based Access Control (RBAC) Manager.

Provides role management and permission checking for API endpoints.
Supports three role levels: admin, user, and read_only.

Security Features:
- Role-based endpoint access control
- API key to role mapping
- Redis-backed role storage
- Permission inheritance (admin > user > read_only)
- Audit logging for role changes

Example Usage:
    rbac_manager = RBACManager(redis_url="redis://localhost:6379/0")
    
    # Assign role to API key
    rbac_manager.assign_role(api_key_hash="abc123...", role="user")
    
    # Check permission
    has_permission = rbac_manager.check_permission(
        api_key_hash="abc123...",
        required_role="user"
    )
"""
import os
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

try:
    import redis
    from redis.connection import ConnectionPool
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from utils.logger import setup_logger

logger = setup_logger(__name__)


def _redact_url_credentials(url: str) -> str:
    """Return URL with username/password removed from netloc for safe logging."""
    try:
        parsed = urlsplit(url)
        if "@" not in parsed.netloc:
            return url
        host_part = parsed.netloc.split("@", 1)[1]
        return urlunsplit((parsed.scheme, host_part, parsed.path, parsed.query, parsed.fragment))
    except Exception:
        return "redacted"


class Role(str, Enum):
    """User role enumeration with permission levels."""
    ADMIN = "admin"          # Full access: all operations
    USER = "user"            # Standard access: queries, memory, session
    READ_ONLY = "read_only"  # Read-only access: queries only
    
    @classmethod
    def from_string(cls, role_str: str) -> Optional['Role']:
        """Convert string to Role enum.
        
        Args:
            role_str: Role name as string
            
        Returns:
            Role enum or None if invalid
        """
        try:
            return cls(role_str.lower())
        except ValueError:
            return None
    
    def __ge__(self, other: 'Role') -> bool:
        """Compare role levels (admin > user > read_only)."""
        hierarchy = {
            Role.READ_ONLY: 1,
            Role.USER: 2,
            Role.ADMIN: 3
        }
        return hierarchy.get(self, 0) >= hierarchy.get(other, 0)


# Default role for unauthenticated/new API keys.
# SECURITY: secure-by-default — an unmapped principal gets the least-privileged
# role (read-only) and must be explicitly elevated to gain write/admin access.
DEFAULT_ROLE = Role.READ_ONLY


# Role-permission mapping for endpoints
ENDPOINT_PERMISSIONS = {
    # Admin-only endpoints
    "/config": Role.ADMIN,
    "/plugins": Role.ADMIN,
    "/admin": Role.ADMIN,
    
    # User endpoints (write operations)
    "/memory/remember": Role.USER,
    "/memory/forget": Role.USER,
    "/cache/clear": Role.USER,
    "/session/clear": Role.USER,
    "/session/save": Role.USER,
    "/session/load": Role.USER,
    
    # Read-only endpoints (all roles)
    "/query": Role.READ_ONLY,
    "/query-adaptive": Role.READ_ONLY,
    "/osint/query": Role.READ_ONLY,
    "/memory/recall": Role.READ_ONLY,
    "/memory/stats": Role.READ_ONLY,
    "/stats": Role.READ_ONLY,
    "/health": Role.READ_ONLY,
    "/api": Role.READ_ONLY,
}


class RBACManager:
    """Role-Based Access Control manager."""
    
    def __init__(
        self,
        redis_url: str | None = None,
        max_connections: int = 50,
        fallback_to_memory: bool = True
    ):
        """Initialize RBAC manager.
        
        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
            max_connections: Maximum Redis connection pool size
            fallback_to_memory: Use in-memory storage if Redis unavailable
        """
        self.fallback_to_memory = fallback_to_memory
        self.memory_roles: dict[str, Role] = {}  # {api_key_hash: Role}
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
                safe_redis_url = _redact_url_credentials(redis_url)
                logger.info(f"RBAC Manager: Redis connected at {safe_redis_url}")
            except Exception as e:
                logger.warning(f"RBAC Manager: Redis connection failed: {e}")
                self.redis_client = None  # Clear redis client on failed connection
                if fallback_to_memory:
                    logger.info("RBAC Manager: Falling back to in-memory storage")
                else:
                    raise
        else:
            logger.warning("RBAC Manager: Redis library not available")
            if not fallback_to_memory:
                raise ImportError("Redis is required but not available")
            logger.info("RBAC Manager: Using in-memory storage")
    
    def assign_role(self, api_key_hash: str, role: Role, user_info: str | None = None) -> bool:
        """Assign a role to an API key.
        
        Args:
            api_key_hash: Hashed API key (user identifier)
            role: Role to assign
            user_info: Optional user information for audit log
            
        Returns:
            True if successful, False otherwise
        """
        if not isinstance(role, Role):
            logger.error(f"Invalid role type: {type(role)}")
            return False
        
        # Store in Redis
        if self.redis_client:
            try:
                key = f"rbac:role:{api_key_hash}"
                self.redis_client.set(key, role.value)
                
                # Store assignment metadata
                metadata_key = f"rbac:meta:{api_key_hash}"
                self.redis_client.hset(metadata_key, mapping={
                    "role": role.value,
                    "assigned_at": datetime.now().isoformat(),
                    "user_info": user_info or "unknown"
                })
                
                actor = "system" if not user_info else "provided"
                logger.info(f"Role assigned: {role.value} by {actor}")
                return True
            except Exception as e:
                logger.error(f"RBAC Manager: Redis role assignment failed: {e}")
                if self.fallback_to_memory:
                    logger.warning("RBAC Manager: Falling back to memory storage")
                else:
                    return False
        
        # Fallback to memory storage
        self.memory_roles[api_key_hash] = role
        logger.info(f"Role assigned (memory): {role.value}")
        return True
    
    def get_role(self, api_key_hash: str) -> Role:
        """Get the role for an API key.
        
        Args:
            api_key_hash: Hashed API key (user identifier)
            
        Returns:
            Role enum (defaults to DEFAULT_ROLE if not found)
        """
        # Check Redis storage
        if self.redis_client:
            try:
                key = f"rbac:role:{api_key_hash}"
                role_str = self.redis_client.get(key)
                
                if role_str:
                    role = Role.from_string(role_str)
                    if role:
                        return role
                    else:
                        logger.warning(f"Invalid role in Redis: {role_str}")
            except Exception as e:
                logger.error(f"RBAC Manager: Redis role retrieval failed: {e}")
                if self.fallback_to_memory:
                    logger.warning("RBAC Manager: Falling back to memory retrieval")
                else:
                    return DEFAULT_ROLE
        
        # Fallback to memory storage
        role = self.memory_roles.get(api_key_hash, DEFAULT_ROLE)
        return role
    
    def check_permission(self, api_key_hash: str, required_role: Role) -> bool:
        """Check if a user has permission for the required role.
        
        Uses role hierarchy: admin >= user >= read_only
        
        Args:
            api_key_hash: Hashed API key (user identifier)
            required_role: Minimum role required
            
        Returns:
            True if user has sufficient permissions, False otherwise
        """
        user_role = self.get_role(api_key_hash)
        has_permission = user_role >= required_role
        
        if not has_permission:
            logger.warning(
                f"Permission denied: user has role {user_role.value}, "
                f"requires {required_role.value}"
            )
        
        return has_permission
    
    def revoke_role(self, api_key_hash: str) -> bool:
        """Revoke (delete) a role assignment.
        
        Args:
            api_key_hash: Hashed API key (user identifier)
            
        Returns:
            True if role was revoked, False if no role existed
        """
        # Revoke from Redis
        if self.redis_client:
            try:
                key = f"rbac:role:{api_key_hash}"
                metadata_key = f"rbac:meta:{api_key_hash}"
                
                count = self.redis_client.delete(key, metadata_key)
                if count > 0:
                    logger.info("Role revoked from Redis")
                    return True
            except Exception as e:
                logger.error(f"RBAC Manager: Redis revocation failed: {e}")
        
        # Revoke from memory
        if api_key_hash in self.memory_roles:
            del self.memory_roles[api_key_hash]
            logger.info("Role revoked from memory")
            return True
        
        return False
    
    def list_roles(self) -> dict[str, str]:
        """List all role assignments.
        
        Returns:
            Dictionary of {api_key_hash: role}
        """
        roles = {}
        
        # Get from Redis
        if self.redis_client:
            try:
                # Scan for all rbac:role:* keys
                for key in self.redis_client.scan_iter("rbac:role:*"):
                    api_key_hash = key.split(":")[-1]
                    role_str = self.redis_client.get(key)
                    roles[api_key_hash] = role_str
            except Exception as e:
                logger.error(f"RBAC Manager: Redis list failed: {e}")
        
        # Merge with memory storage
        for api_key_hash, role in self.memory_roles.items():
            if api_key_hash not in roles:
                roles[api_key_hash] = role.value
        
        return roles
    
    def get_endpoint_required_role(self, endpoint: str, method: str) -> Role | None:
        """Get the required role for an endpoint.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            
        Returns:
            Required role or None if no restriction
        """
        # Exact match
        if endpoint in ENDPOINT_PERMISSIONS:
            return ENDPOINT_PERMISSIONS[endpoint]
        
        # Prefix match for dynamic endpoints
        for pattern, role in ENDPOINT_PERMISSIONS.items():
            if endpoint.startswith(pattern):
                return role
        
        # Default: require USER role for state-changing methods
        if method in ["POST", "PUT", "PATCH", "DELETE"]:
            return Role.USER
        
        # GET/HEAD/OPTIONS: allow all roles
        return Role.READ_ONLY
    
    def get_stats(self) -> dict[str, Any]:
        """Get RBAC manager statistics.
        
        Returns:
            Dictionary with role counts and configuration
        """
        stats = {
            "backend": "redis" if self.using_redis else "memory",
            "default_role": DEFAULT_ROLE.value,
            "memory_role_count": len(self.memory_roles),
        }
        
        if self.redis_client and self.using_redis:
            try:
                # Count role keys in Redis
                role_keys = list(self.redis_client.scan_iter("rbac:role:*"))
                stats["redis_role_count"] = len(role_keys)
                
                # Count roles by type
                role_counts = {"admin": 0, "user": 0, "read_only": 0}
                for key in role_keys:
                    role_str = self.redis_client.get(key)
                    if role_str in role_counts:
                        role_counts[role_str] += 1
                
                stats["role_distribution"] = role_counts
            except Exception as e:
                logger.error(f"RBAC Manager: Failed to get Redis stats: {e}")
                stats["redis_error"] = str(e)
        
        return stats


# Global RBAC manager instance
_rbac_manager: RBACManager | None = None


def get_rbac_manager() -> RBACManager:
    """Get the global RBAC manager instance.
    
    Initializes on first call with default configuration.
    """
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager


def get_role_hierarchy() -> list[str]:
    """Get role hierarchy list (highest to lowest).
    
    Returns:
        List of role names in descending order of permissions
    """
    return [Role.ADMIN.value, Role.USER.value, Role.READ_ONLY.value]
