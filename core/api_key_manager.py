"""API Key Rotation Manager.

Provides secure API key lifecycle management with support for:
- Multiple active keys per user
- Graceful key rotation without downtime  
- Key expiration and auto-revocation
- Key usage tracking
- Audit trail for key operations

Security Features:
- Multiple concurrent active keys (blue-green rotation)
- Key expiration timestamps
- Created/last-used tracking
- Redis-backed storage for distributed deployments
- HMAC-based key hashing for secure storage

Example Usage:
    key_manager = APIKeyManager()
    
    # Generate new key
    new_key = key_manager.generate_key(user_id="user_123")
    
    # Validate key
    is_valid, user_id = key_manager.validate_key(api_key="...")
    
    # Rotate keys
    old_key = "..."
    new_key = key_manager.rotate_key(old_key)
"""
import os
import secrets
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json

try:
    import redis
    from redis.connection import ConnectionPool
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from utils.logger import setup_logger
from utils.secure_hash import hmac_sha256_hex

logger = setup_logger(__name__)


class APIKey:
    """Represents an API key with metadata."""
    
    def __init__(
        self,
        key_id: str,
        key_hash: str,
        user_id: str,
        created_at: datetime,
        expires_at: Optional[datetime] = None,
        last_used: Optional[datetime] = None,
        is_active: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.key_id = key_id
        self.key_hash = key_hash
        self.user_id = user_id
        self.created_at = created_at
        self.expires_at = expires_at
        self.last_used = last_used
        self.is_active = is_active
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "key_id": self.key_id,
            "key_hash": self.key_hash,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "is_active": self.is_active,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'APIKey':
        """Create from dictionary."""
        return cls(
            key_id=data["key_id"],
            key_hash=data["key_hash"],
            user_id=data["user_id"],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
            is_active=data.get("is_active", True),
            metadata=data.get("metadata", {})
        )
    
    def is_expired(self) -> bool:
        """Check if key is expired."""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at


class APIKeyManager:
    """Manage API key lifecycle with rotation support."""
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        max_keys_per_user: int = 5,
        default_expiry_days: int = 90,
        fallback_to_file: bool = True,
        storage_file: str = "data/api_keys.json"
    ):
        """Initialize API key manager.
        
        Args:
            redis_url: Redis connection URL
            max_keys_per_user: Maximum active keys per user
            default_expiry_days: Default key expiration in days (0 = no expiry)
            fallback_to_file: Use file storage if Redis unavailable
            storage_file: File path for fallback storage
        """
        self.max_keys_per_user = max_keys_per_user
        self.default_expiry_days = default_expiry_days
        self.fallback_to_file = fallback_to_file
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Secret for key hashing
        self.secret = os.getenv("RATE_LIMIT_SECRET", secrets.token_bytes(32))
        if isinstance(self.secret, str):
            self.secret = self.secret.encode('utf-8')
        
        # Initialize Redis
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
                pool = ConnectionPool.from_url(
                    redis_url,
                    max_connections=50,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                self.redis_client = redis.Redis(connection_pool=pool)
                self.redis_client.ping()
                logger.info(f"API Key Manager: Redis connected at {redis_url}")
            except Exception as e:
                logger.warning(f"API Key Manager: Redis connection failed: {e}")
                if fallback_to_file:
                    logger.info("API Key Manager: Using file-based storage")
                else:
                    raise
        else:
            logger.warning("API Key Manager: Redis not available")
            if not fallback_to_file:
                raise ImportError("Redis required but not available")
            logger.info("API Key Manager: Using file-based storage")
    
    def _hash_key(self, api_key: str) -> str:
        """Hash API key for secure storage."""
        return hmac_sha256_hex(api_key, key=self.secret)
    
    def generate_key(
        self,
        user_id: str,
        expiry_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """Generate a new API key.
        
        Args:
            user_id: User identifier
            expiry_days: Days until expiration (None = use default, 0 = no expiry)
            metadata: Optional key metadata
            
        Returns:
            Tuple of (plaintext_key, key_id)
        """
        # Check key limit
        active_keys = self.list_keys(user_id, active_only=True)
        if len(active_keys) >= self.max_keys_per_user:
            raise ValueError(f"User already has maximum of {self.max_keys_per_user} active keys")
        
        # Generate key
        plaintext_key = secrets.token_urlsafe(32)
        key_hash = self._hash_key(plaintext_key)
        key_id = secrets.token_urlsafe(16)
        
        # Calculate expiry
        expiry_days = expiry_days if expiry_days is not None else self.default_expiry_days
        expires_at = datetime.now() + timedelta(days=expiry_days) if expiry_days > 0 else None
        
        # Create API key object
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            user_id=user_id,
            created_at=datetime.now(),
            expires_at=expires_at,
            metadata=metadata or {}
        )
        
        # Store key
        self._store_key(api_key)
        
        logger.info(f"Generated API key, expires: {expires_at}")
        
        return plaintext_key, key_id
    
    def validate_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate an API key.
        
        Args:
            api_key: Plaintext API key
            
        Returns:
            Tuple of (is_valid, user_id)
        """
        key_hash = self._hash_key(api_key)
        
        # Find key by hash
        stored_key = self._get_key_by_hash(key_hash)
        
        if not stored_key:
            return False, None
        
        # Check if active
        if not stored_key.is_active:
            logger.warning(f"Inactive API key used: {stored_key.key_id}")
            return False, None
        
        # Check if expired
        if stored_key.is_expired():
            logger.warning(f"Expired API key used: {stored_key.key_id}")
            # Auto-revoke expired key
            self.revoke_key(stored_key.key_id)
            return False, None
        
        # Update last used
        self._update_last_used(stored_key.key_id)
        
        return True, stored_key.user_id
    
    def rotate_key(
        self,
        old_key: str,
        expiry_days: Optional[int] = None
    ) -> Tuple[str, str]:
        """Rotate an API key (generate new, keep old active temporarily).
        
        Args:
            old_key: Current API key to rotate
            expiry_days: Days until new key expiration
            
        Returns:
            Tuple of (new_plaintext_key, new_key_id)
        """
        # Validate old key
        is_valid, user_id = self.validate_key(old_key)
        if not is_valid:
            raise ValueError("Invalid or expired API key")
        
        # Generate new key
        new_key, new_key_id = self.generate_key(
            user_id=user_id,
            expiry_days=expiry_days,
            metadata={"rotated_from": self._hash_key(old_key)}
        )
        
        logger.info(f"Rotated API key for user {user_id[:8]}..., new key_id: {new_key_id}")
        
        return new_key, new_key_id
    
    def revoke_key(self, key_id: str) -> bool:
        """Revoke (deactivate) an API key.
        
        Args:
            key_id: Key ID to revoke
            
        Returns:
            True if revoked, False if not found
        """
        stored_key = self._get_key_by_id(key_id)
        
        if not stored_key:
            return False
        
        stored_key.is_active = False
        self._store_key(stored_key)
        
        logger.info(f"Revoked API key: {key_id}")
        return True
    
    def list_keys(
        self,
        user_id: str,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """List API keys for a user.
        
        Args:
            user_id: User identifier
            active_only: Only return active keys
            
        Returns:
            List of key metadata (no plaintext keys)
        """
        keys = self._get_keys_by_user(user_id)
        
        if active_only:
            keys = [k for k in keys if k.is_active and not k.is_expired()]
        
        # Convert to display format (hide key hash)
        result = []
        for key in keys:
            result.append({
                "key_id": key.key_id,
                "created_at": key.created_at.isoformat() if key.created_at else None,
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "last_used": key.last_used.isoformat() if key.last_used else None,
                "is_active": key.is_active,
                "is_expired": key.is_expired(),
                "metadata": key.metadata
            })
        
        return result
    
    def _store_key(self, api_key: APIKey):
        """Store API key (Redis or file)."""
        if self.redis_client:
            try:
                key = f"apikey:hash:{api_key.key_hash}"
                self.redis_client.set(key, json.dumps(api_key.to_dict()))
                
                # Also index by key_id for lookups
                id_key = f"apikey:id:{api_key.key_id}"
                self.redis_client.set(id_key, api_key.key_hash)
                
                # Index by user for listing
                user_key = f"apikey:user:{api_key.user_id}"
                self.redis_client.sadd(user_key, api_key.key_id)
                
                logger.debug(f"Stored API key in Redis: {api_key.key_id}")
                return
            except Exception as e:
                logger.error(f"Failed to store key in Redis: {e}")
        
        # Fallback to file storage
        self._store_key_file(api_key)
    
    def _store_key_file(self, api_key: APIKey):
        """Store API key in file."""
        keys = {}
        if self.storage_file.exists():
            with open(self.storage_file, 'r') as f:
                keys = json.load(f)
        
        keys[api_key.key_hash] = api_key.to_dict()
        
        with open(self.storage_file, 'w') as f:
            json.dump(keys, f, indent=2)
    
    def _get_key_by_hash(self, key_hash: str) -> Optional[APIKey]:
        """Get API key by hash."""
        if self.redis_client:
            try:
                key = f"apikey:hash:{key_hash}"
                data = self.redis_client.get(key)
                if data:
                    return APIKey.from_dict(json.loads(data))
            except Exception as e:
                logger.error(f"Failed to get key from Redis: {e}")
        
        # Fallback to file
        if self.storage_file.exists():
            with open(self.storage_file, 'r') as f:
                keys = json.load(f)
                if key_hash in keys:
                    return APIKey.from_dict(keys[key_hash])
        
        return None
    
    def _get_key_by_id(self, key_id: str) -> Optional[APIKey]:
        """Get API key by ID."""
        if self.redis_client:
            try:
                id_key = f"apikey:id:{key_id}"
                key_hash = self.redis_client.get(id_key)
                if key_hash:
                    return self._get_key_by_hash(key_hash)
            except Exception as e:
                logger.error(f"Failed to get key from Redis: {e}")
        
        # Fallback to file (scan all keys)
        if self.storage_file.exists():
            with open(self.storage_file, 'r') as f:
                keys = json.load(f)
                for key_data in keys.values():
                    if key_data.get("key_id") == key_id:
                        return APIKey.from_dict(key_data)
        
        return None
    
    def _get_keys_by_user(self, user_id: str) -> List[APIKey]:
        """Get all keys for a user."""
        result = []
        
        if self.redis_client:
            try:
                user_key = f"apikey:user:{user_id}"
                key_ids = self.redis_client.smembers(user_key)
                for key_id in key_ids:
                    key = self._get_key_by_id(key_id)
                    if key:
                        result.append(key)
                return result
            except Exception as e:
                logger.error(f"Failed to get user keys from Redis: {e}")
        
        # Fallback to file (scan all)
        if self.storage_file.exists():
            with open(self.storage_file, 'r') as f:
                keys = json.load(f)
                for key_data in keys.values():
                    if key_data.get("user_id") == user_id:
                        result.append(APIKey.from_dict(key_data))
        
        return result
    
    def _update_last_used(self, key_id: str):
        """Update last used timestamp."""
        key = self._get_key_by_id(key_id)
        if key:
            key.last_used = datetime.now()
            self._store_key(key)


# Global API key manager instance
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager
