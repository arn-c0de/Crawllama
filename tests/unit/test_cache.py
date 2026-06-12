"""Tests for cache functionality."""
import tempfile

import pytest

from core.cache import CacheManager


@pytest.fixture
def temp_cache():
    """Create temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = CacheManager(cache_dir=tmpdir, ttl_hours=1)
        yield cache


def test_cache_set_and_get(temp_cache):
    """Test setting and getting cache."""
    temp_cache.set("test_key", {"data": "test_value"})

    result = temp_cache.get("test_key")
    assert result is not None
    assert result["data"] == "test_value"


def test_cache_miss(temp_cache):
    """Test cache miss."""
    result = temp_cache.get("nonexistent_key")
    assert result is None


def test_cache_clear(temp_cache):
    """Test clearing cache."""
    temp_cache.set("key1", {"data": "value1"})
    temp_cache.set("key2", {"data": "value2"})

    count = temp_cache.clear()
    assert count == 2

    assert temp_cache.get("key1") is None
    assert temp_cache.get("key2") is None


def test_cache_stats(temp_cache):
    """Test cache statistics."""
    temp_cache.set("key1", {"data": "value1"})

    stats = temp_cache.get_stats()
    assert stats["total_files"] >= 1
    assert "total_size_bytes" in stats
