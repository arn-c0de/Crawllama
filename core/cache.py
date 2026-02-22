"""Cache manager for web content and search results."""
import json
import hashlib
import logging
from collections import OrderedDict
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any, Dict

logger = logging.getLogger("crawllama")

# Maximum entries in the in-memory LRU cache
_MEM_LRU_MAX = 128


class CacheManager:
    """Manages caching of web content with TTL and size limits.

    Uses a two-tier strategy: an in-memory LRU for hot entries and
    filesystem-backed JSON files for persistence.
    """

    def __init__(self, cache_dir: str = "data/cache", ttl_hours: int = 24, max_size_mb: int = 500):
        """
        Initialize cache manager with size limits.

        Args:
            cache_dir: Directory to store cache files
            ttl_hours: Time-to-live in hours
            max_size_mb: Maximum cache size in megabytes (default: 500MB)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self.max_size_bytes = max_size_mb * 1024 * 1024  # Convert MB to bytes
        # In-memory LRU: key_hash -> (timestamp, content)
        self._mem_cache: OrderedDict[str, tuple[datetime, Any]] = OrderedDict()
        logger.info(f"Cache initialized: {self.cache_dir} (TTL: {ttl_hours}h, Max size: {max_size_mb}MB)")

    def _get_key(self, identifier: str) -> str:
        """
        Generate hash key for cache file.

        Args:
            identifier: Unique identifier (URL, query, etc.)

        Returns:
            MD5 hash of identifier
        """
        # Non-cryptographic usage: stable, compact cache filename derivation.
        return hashlib.md5(identifier.encode("utf-8"), usedforsecurity=False).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve value from cache if not expired.

        Checks in-memory LRU first, then falls back to disk.

        Args:
            key: Cache key (URL, query, etc.)

        Returns:
            Cached content or None if expired/not found
        """
        key_hash = self._get_key(key)

        # Check in-memory LRU first
        if key_hash in self._mem_cache:
            ts, content = self._mem_cache[key_hash]
            if datetime.now() - ts <= self.ttl:
                self._mem_cache.move_to_end(key_hash)
                logger.debug(f"Cache hit (memory): {key}")
                return content
            else:
                del self._mem_cache[key_hash]

        cache_file = self.cache_dir / f"{key_hash}.json"

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

            # Promote to in-memory LRU
            self._mem_cache_put(key_hash, cached_time, data["content"])

            logger.debug(f"Cache hit (disk): {key}")
            return data["content"]

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Cache read error: {e}")
            cache_file.unlink()  # Delete corrupted cache
            return None

    def _mem_cache_put(self, key_hash: str, timestamp: datetime, content: Any):
        """Add entry to in-memory LRU, evicting oldest if at capacity."""
        self._mem_cache[key_hash] = (timestamp, content)
        self._mem_cache.move_to_end(key_hash)
        while len(self._mem_cache) > _MEM_LRU_MAX:
            self._mem_cache.popitem(last=False)

    def set(self, key: str, content: Any) -> None:
        """
        Store value in cache with automatic size management.

        Args:
            key: Cache key
            content: Content to cache (must be JSON-serializable)
        """
        key_hash = self._get_key(key)
        cache_file = self.cache_dir / f"{key_hash}.json"
        now = datetime.now()

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": now.isoformat(),
                    "key": key,
                    "content": content
                }, f, ensure_ascii=False, indent=2)

            # Populate in-memory LRU
            self._mem_cache_put(key_hash, now, content)

            logger.debug(f"Cached: {key}")

            # Enforce cache size limit after adding new entry
            self._enforce_cache_limit()

        except (TypeError, ValueError) as e:
            logger.error(f"Cache write error: {e}")

    def _enforce_cache_limit(self) -> None:
        """
        Enforce cache size limit using LRU (Least Recently Used) eviction.

        Deletes oldest cache files if total size exceeds max_size_bytes.
        Uses a single stat() pass to avoid redundant filesystem calls.
        """
        # Single stat() pass: collect (path, size, mtime) tuples
        file_info = []
        total_size = 0
        for f in self.cache_dir.glob("*.json"):
            try:
                st = f.stat()
                file_info.append((f, st.st_size, st.st_mtime))
                total_size += st.st_size
            except OSError:
                continue

        if total_size <= self.max_size_bytes:
            return  # Within limit, nothing to do

        # Sort by modification time (oldest first)
        file_info.sort(key=lambda x: x[2])

        # Delete oldest files until we're under the limit
        freed_bytes = 0
        deleted_count = 0
        for cache_file, file_size, _ in file_info:
            if total_size <= self.max_size_bytes:
                break

            try:
                cache_file.unlink()
                # Evict from memory LRU too
                key_hash = cache_file.stem
                self._mem_cache.pop(key_hash, None)
            except OSError:
                continue
            total_size -= file_size
            freed_bytes += file_size
            deleted_count += 1

        if deleted_count > 0:
            logger.info(
                f"Cache limit enforcement: deleted {deleted_count} old entries "
                f"(freed {freed_bytes / (1024 * 1024):.2f} MB)"
            )

    def clear(self) -> int:
        """
        Clear all cache files and in-memory LRU.

        Returns:
            Number of files deleted
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1

        self._mem_cache.clear()
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
            "memory_entries": len(self._mem_cache),
            "memory_max": _MEM_LRU_MAX,
            "cache_dir": str(self.cache_dir)
        }

    async def async_get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Async version of get(). Uses aiofiles for non-blocking I/O.

        Checks in-memory LRU first, then falls back to disk.
        """
        key_hash = self._get_key(key)

        # Check in-memory LRU first
        if key_hash in self._mem_cache:
            ts, content = self._mem_cache[key_hash]
            if datetime.now() - ts <= self.ttl:
                self._mem_cache.move_to_end(key_hash)
                logger.debug(f"Cache hit (memory): {key}")
                return content
            else:
                del self._mem_cache[key_hash]

        try:
            import aiofiles
        except ImportError:
            logger.error("aiofiles not installed. Async cache unavailable.")
            return None
        cache_file = self.cache_dir / f"{key_hash}.json"
        if not cache_file.exists():
            logger.debug(f"Cache miss: {key}")
            return None
        try:
            async with aiofiles.open(cache_file, "r", encoding="utf-8") as f:
                data = json.loads(await f.read())
            cached_time = datetime.fromisoformat(data["timestamp"])
            if datetime.now() - cached_time > self.ttl:
                logger.debug(f"Cache expired: {key}")
                cache_file.unlink()
                return None

            # Promote to in-memory LRU
            self._mem_cache_put(key_hash, cached_time, data["content"])

            logger.debug(f"Cache hit (disk): {key}")
            return data["content"]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Cache read error: {e}")
            cache_file.unlink()
            return None

    async def async_set(self, key: str, content: Any) -> None:
        """
        Async version of set(). Uses aiofiles for non-blocking I/O.
        """
        try:
            import aiofiles
        except ImportError:
            logger.error("aiofiles not installed. Async cache unavailable.")
            return
        key_hash = self._get_key(key)
        cache_file = self.cache_dir / f"{key_hash}.json"
        now = datetime.now()
        data = {
            "timestamp": now.isoformat(),
            "key": key,
            "content": content
        }
        async with aiofiles.open(cache_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))

        # Populate in-memory LRU
        self._mem_cache_put(key_hash, now, content)

        # Enforce disk size limit (sync — acceptable since eviction is rare)
        self._enforce_cache_limit()
