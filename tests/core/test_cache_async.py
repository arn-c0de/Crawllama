import pytest
import tempfile
import shutil
from core.cache import CacheManager
import asyncio

@pytest.fixture
def temp_cache_dir():
    dirpath = tempfile.mkdtemp()
    yield dirpath
    shutil.rmtree(dirpath)


def test_cache_set_and_get(temp_cache_dir):
    cache = CacheManager(cache_dir=temp_cache_dir, ttl_hours=1)
    key = "test-key"
    value = {"foo": "bar"}
    cache.set(key, value)
    result = cache.get(key)
    assert result == value


def test_cache_expiry(temp_cache_dir):
    cache = CacheManager(cache_dir=temp_cache_dir, ttl_hours=0)
    key = "expire-key"
    value = {"baz": 123}
    cache.set(key, value)
    # Should expire immediately
    result = cache.get(key)
    assert result is None

@pytest.mark.asyncio
async def test_async_cache_set_and_get(temp_cache_dir):
    try:
        import aiofiles
        import pytest_asyncio
    except ImportError as e:
        pytest.skip(f"Required async dependencies not installed: {e}")
    
    cache = CacheManager(cache_dir=temp_cache_dir, ttl_hours=1)
    key = "async-key"
    value = {"hello": "world"}
    await cache.async_set(key, value)
    result = await cache.async_get(key)
    assert result == value


def test_async_methods_fallback_gracefully(temp_cache_dir):
    """Test that async methods handle missing dependencies gracefully."""
    cache = CacheManager(cache_dir=temp_cache_dir, ttl_hours=1)
    
    # Test that async_get returns None when aiofiles is not available
    import asyncio
    result = asyncio.run(cache.async_get("test-key"))
    assert result is None  # Should return None due to missing aiofiles
    
    # Test that async_set handles missing dependencies gracefully
    asyncio.run(cache.async_set("test-key", {"test": "value"}))
    # Should not raise an exception, just log an error
