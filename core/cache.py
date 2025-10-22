"""Cache manager for web content and search results."""
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any, Dict

logger = logging.getLogger("crawllama")


class CacheManager:
    """Manages caching of web content with TTL support."""

    def __init__(self, cache_dir: str = "data/cache", ttl_hours: int = 24):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory to store cache files
            ttl_hours: Time-to-live in hours
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        logger.info(f"Cache initialized: {self.cache_dir} (TTL: {ttl_hours}h)")

    def _get_key(self, identifier: str) -> str:
        """
        Generate hash key for cache file.

        Args:
            identifier: Unique identifier (URL, query, etc.)

        Returns:
            MD5 hash of identifier
        """
        return hashlib.md5(identifier.encode()).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve value from cache if not expired.

        Args:
            key: Cache key (URL, query, etc.)

        Returns:
            Cached content or None if expired/not found
        """
        cache_file = self.cache_dir / f"{self._get_key(key)}.json"

        if not cache_file.exists():
            logger.debug(f"Cache miss: {key}")
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check TTL
            cached_time = datetime.fromisoformat(data["timestamp"])
            if datetime.now() - cached_time > self.ttl:
                logger.debug(f"Cache expired: {key}")
                cache_file.unlink()  # Delete expired cache
                return None

            logger.debug(f"Cache hit: {key}")
            return data["content"]

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Cache read error: {e}")
            cache_file.unlink()  # Delete corrupted cache
            return None

    def set(self, key: str, content: Any) -> None:
        """
        Store value in cache.

        Args:
            key: Cache key
            content: Content to cache (must be JSON-serializable)
        """
        cache_file = self.cache_dir / f"{self._get_key(key)}.json"

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "key": key,
                    "content": content
                }, f, ensure_ascii=False, indent=2)

            logger.debug(f"Cached: {key}")

        except (TypeError, ValueError) as e:
            logger.error(f"Cache write error: {e}")

    def clear(self) -> int:
        """
        Clear all cache files.

        Returns:
            Number of files deleted
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1

        logger.info(f"Cache cleared: {count} files deleted")
        return count

    def clear_expired(self) -> int:
        """
        Clear only expired cache files.

        Returns:
            Number of expired files deleted
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                cached_time = datetime.fromisoformat(data["timestamp"])
                if datetime.now() - cached_time > self.ttl:
                    cache_file.unlink()
                    count += 1

            except Exception as e:
                logger.error(f"Error checking cache file {cache_file}: {e}")
                cache_file.unlink()
                count += 1

        logger.info(f"Expired cache cleared: {count} files deleted")
        return count

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)

        return {
            "total_files": len(files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_dir": str(self.cache_dir)
        }
