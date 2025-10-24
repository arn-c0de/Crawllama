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
    cache = CacheManager(cache_dir=temp_cache_dir, ttl_hours=1)
    key = "async-key"
    value = {"hello": "world"}
    await cache.async_set(key, value)
    result = await cache.async_get(key)
    assert result == value
