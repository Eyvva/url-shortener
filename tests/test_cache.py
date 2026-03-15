"""Тесты кэширования Redis."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.cache import (
    cache_set, cache_get, cache_delete, cache_increment,
    redirect_key, stats_key, search_key,
)



def test_redirect_key():
    assert redirect_key("abc123") == "redirect:abc123"


def test_stats_key():
    assert stats_key("abc123") == "stats:abc123"


def test_search_key():
    assert search_key("https://example.com") == "search:https://example.com"



@pytest.mark.asyncio
async def test_cache_set_and_get():
    fake = {"_store": {}}

    async def fake_set(key, value, ex=None):
        fake["_store"][key] = value

    async def fake_get(key):
        return fake["_store"].get(key)

    mock_redis = AsyncMock()
    mock_redis.set = fake_set
    mock_redis.get = fake_get

    with patch("app.core.cache.get_redis", return_value=mock_redis):
        await cache_set("test_key", {"data": 42}, ttl=60)
        result = await cache_get("test_key")
        assert result == {"data": 42}


@pytest.mark.asyncio
async def test_cache_get_missing_key():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    with patch("app.core.cache.get_redis", return_value=mock_redis):
        result = await cache_get("nonexistent_key")
        assert result is None


@pytest.mark.asyncio
async def test_cache_delete():
    deleted = []

    async def fake_delete(*keys):
        deleted.extend(keys)

    mock_redis = AsyncMock()
    mock_redis.delete = fake_delete

    with patch("app.core.cache.get_redis", return_value=mock_redis):
        await cache_delete("key1", "key2")
        assert "key1" in deleted
        assert "key2" in deleted


@pytest.mark.asyncio
async def test_cache_increment():
    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=5)

    with patch("app.core.cache.get_redis", return_value=mock_redis):
        result = await cache_increment("counter_key")
        assert result == 5


@pytest.mark.asyncio
async def test_cache_set_stores_json():
    stored = {}

    async def fake_set(key, value, ex=None):
        stored[key] = value

    async def fake_get(key):
        return stored.get(key)

    mock_redis = AsyncMock()
    mock_redis.set = fake_set
    mock_redis.get = fake_get

    with patch("app.core.cache.get_redis", return_value=mock_redis):
        await cache_set("json_key", [1, 2, 3])
        result = await cache_get("json_key")
        assert result == [1, 2, 3]



@pytest.mark.asyncio
async def test_get_redis_creates_new_client_when_none():
    """get_redis должен создавать новый клиент, если _redis_client is None."""
    import app.core.cache as cache_module

    old_client = cache_module._redis_client
    cache_module._redis_client = None
    try:
        mock_redis = MagicMock()
        with patch("app.core.cache.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            result = await cache_module.get_redis()

        assert result is mock_redis
        assert cache_module._redis_client is mock_redis
        mock_aioredis.from_url.assert_called_once()
    finally:
        cache_module._redis_client = old_client


@pytest.mark.asyncio
async def test_get_redis_reuses_existing_client():
    """get_redis должен возвращать существующий клиент без повторного создания."""
    import app.core.cache as cache_module

    old_client = cache_module._redis_client
    mock_existing = MagicMock()
    cache_module._redis_client = mock_existing
    try:
        result = await cache_module.get_redis()
        assert result is mock_existing
    finally:
        cache_module._redis_client = old_client


@pytest.mark.asyncio
async def test_close_redis_closes_and_clears():
    """close_redis должен вызвать aclose() и обнулить _redis_client."""
    import app.core.cache as cache_module

    old_client = cache_module._redis_client
    mock_redis = AsyncMock()
    mock_redis.aclose = AsyncMock()
    cache_module._redis_client = mock_redis
    try:
        await cache_module.close_redis()
        mock_redis.aclose.assert_called_once()
        assert cache_module._redis_client is None
    finally:
        cache_module._redis_client = old_client


@pytest.mark.asyncio
async def test_close_redis_noop_when_none():
    """close_redis не должен падать, если _redis_client уже None."""
    import app.core.cache as cache_module

    old_client = cache_module._redis_client
    cache_module._redis_client = None
    try:
        await cache_module.close_redis()  
        assert cache_module._redis_client is None
    finally:
        cache_module._redis_client = old_client
