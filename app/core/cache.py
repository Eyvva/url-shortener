import json
from typing import Any, Optional
import redis.asyncio as aioredis
from app.core.config import settings


_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None




def redirect_key(short_code: str) -> str:
    return f"redirect:{short_code}"


def stats_key(short_code: str) -> str:
    return f"stats:{short_code}"


def search_key(original_url: str) -> str:
    return f"search:{original_url}"




async def cache_set(key: str, value: Any, ttl: int = settings.CACHE_TTL) -> None:
    r = await get_redis()
    await r.set(key, json.dumps(value), ex=ttl)


async def cache_get(key: str) -> Optional[Any]:
    r = await get_redis()
    data = await r.get(key)
    if data:
        return json.loads(data)
    return None


async def cache_delete(*keys: str) -> None:
    r = await get_redis()
    if keys:
        await r.delete(*keys)


async def cache_increment(key: str) -> int:
    """Atomic increment; used for click-counting in cache."""
    r = await get_redis()
    return await r.incr(key)
