"""Cache manager for web content and search results."""
import hashlib
import json
import logging
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core import telemetry

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

    @classmethod
    def from_config(cls, config: dict) -> "CacheManager":
        """Build the cache from config.json settings (paths.cache_dir, cache.*)."""
        cache_config = config.get("cache", {})
        return cls(
            cache_dir=config.get("paths", {}).get("cache_dir", "data/cache"),
            ttl_hours=cache_config.get("ttl_hours", 24),
            max_size_mb=cache_config.get("max_size_mb", 500),
        )

    def _get_key(self, identifier: str) -> str:
        """
        Generate hash key for cache file.

        Args:
            identifier: Unique identifier (URL, query, etc.)

        Returns:
            SHA-256 hash of identifier
        """
        return hashlib.sha256(identifier.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        """
        Retrieve value from cache if not expired.

        Checks in-memory LRU first, then falls back to disk.

        Args:
            key: Cache key (URL, query, etc.)

        Returns:
            Cached content or None if expired/not found
        """
        key_hash = self._get_key(key)
        found, content = self._mem_lookup(key_hash, key)
        if found:
            return content

        cache_file = self.cache_dir / f"{key_hash}.json"
        if not cache_file.exists():
            logger.debug(f"Cache miss: {key}")
            telemetry.emit("cache.lookup", **{"outcome": "miss", "tier": "disk", "arena.key_digest": key_hash[:12]})
            return None

        try:
            raw = cache_file.read_text(encoding="utf-8")
        except OSError as e:
            logger.error(f"Cache read error: {e}")
            return None
        return self._decode_entry(raw, cache_file, key, key_hash)

    def _mem_lookup(self, key_hash: str, key: str) -> tuple[bool, Any]:
        """Return (found, content) from the in-memory LRU, dropping expired entries."""
        entry = self._mem_cache.get(key_hash)
        if entry is None:
            return False, None
        ts, content = entry
        if datetime.now() - ts > self.ttl:
            self._mem_cache.pop(key_hash, None)
            return False, None
        self._mem_cache.move_to_end(key_hash)
        logger.debug(f"Cache hit (memory): {key}")
        telemetry.emit("cache.lookup", **{"outcome": "hit", "tier": "memory", "arena.key_digest": key_hash[:12]})
        return True, content

    def _decode_entry(self, raw: str, cache_file: Path, key: str, key_hash: str) -> Any:
        """Decode a disk entry: TTL check, LRU promotion, corrupt-file cleanup."""
        try:
            data = json.loads(raw)
            cached_time = datetime.fromisoformat(data["timestamp"])
            content = data["content"]
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.error(f"Cache read error: {e}")
            cache_file.unlink(missing_ok=True)  # Delete corrupted cache
            telemetry.emit("cache.lookup", **{"outcome": "corrupt", "tier": "disk", "arena.key_digest": key_hash[:12]})
            return None

        if datetime.now() - cached_time > self.ttl:
            logger.debug(f"Cache expired: {key}")
            cache_file.unlink(missing_ok=True)  # Delete expired cache
            telemetry.emit("cache.lookup", **{"outcome": "expired", "tier": "disk", "arena.key_digest": key_hash[:12]})
            return None

        self._mem_cache_put(key_hash, cached_time, content)
        logger.debug(f"Cache hit (disk): {key}")
        telemetry.emit("cache.lookup", **{"outcome": "hit", "tier": "disk", "arena.key_digest": key_hash[:12]})
        return content

    @staticmethod
    def _serialize_entry(key: str, content: Any, now: datetime) -> str:
        """JSON text of a cache entry (raises TypeError/ValueError if not serializable)."""
        return json.dumps({"timestamp": now.isoformat(), "key": key, "content": content}, ensure_ascii=False, indent=2)

    @staticmethod
    def _tmp_path(cache_file: Path) -> Path:
        """Unique temp file next to the entry, so concurrent writers never collide."""
        return cache_file.with_name(f"{cache_file.stem}.{uuid.uuid4().hex}.tmp")

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
            payload = self._serialize_entry(key, content, now)
            # Atomic write (tmp + rename): a crash mid-write cannot leave a
            # truncated cache entry behind.
            tmp_file = self._tmp_path(cache_file)
            tmp_file.write_text(payload, encoding="utf-8")
            tmp_file.replace(cache_file)
        except (TypeError, ValueError, OSError) as e:
            logger.error(f"Cache write error: {e}")
            return

        self._mem_cache_put(key_hash, now, content)
        logger.debug(f"Cached: {key}")
        self._enforce_cache_limit()

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
                with open(cache_file, encoding="utf-8") as f:
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

    def get_stats(self) -> dict[str, Any]:
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

    async def async_get(self, key: str) -> dict[str, Any] | None:
        """
        Async version of get(). Uses aiofiles for non-blocking I/O.

        Checks in-memory LRU first, then falls back to disk.
        """
        key_hash = self._get_key(key)
        found, content = self._mem_lookup(key_hash, key)
        if found:
            return content

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
            async with aiofiles.open(cache_file, encoding="utf-8") as f:
                raw = await f.read()
        except OSError as e:
            logger.error(f"Cache read error: {e}")
            return None
        return self._decode_entry(raw, cache_file, key, key_hash)

    async def async_set(self, key: str, content: Any) -> None:
        """
        Async version of set(). Uses aiofiles for non-blocking I/O.

        Writes atomically like set(), so a concurrent reader never sees a
        half-written entry (which it would delete as corrupt).
        """
        try:
            import aiofiles
        except ImportError:
            logger.error("aiofiles not installed. Async cache unavailable.")
            return
        key_hash = self._get_key(key)
        cache_file = self.cache_dir / f"{key_hash}.json"
        now = datetime.now()
        try:
            payload = self._serialize_entry(key, content, now)
            tmp_file = self._tmp_path(cache_file)
            async with aiofiles.open(tmp_file, "w", encoding="utf-8") as f:
                await f.write(payload)
            tmp_file.replace(cache_file)
        except (TypeError, ValueError, OSError) as e:
            logger.error(f"Cache write error: {e}")
            return

        # Populate in-memory LRU
        self._mem_cache_put(key_hash, now, content)

        # Enforce disk size limit (sync — acceptable since eviction is rare)
        self._enforce_cache_limit()
