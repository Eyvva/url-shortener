"""Тесты редиректа и кэширования популярных ссылок."""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_redirect_updates_last_used_at(client: AsyncClient):
    resp = await client.post(
        "/api/v1/links/shorten",
        json={"original_url": "https://last-used.example.com"},
    )
    code = resp.json()["short_code"]
    assert resp.json()["last_used_at"] is None

    await client.get(f"/{code}", follow_redirects=False)

    stats = await client.get(f"/api/v1/links/{code}/stats")
    assert stats.json()["last_used_at"] is not None


@pytest.mark.asyncio
async def test_redirect_expired_link_returns_404(client: AsyncClient):
    resp = await client.post(
        "/api/v1/links/shorten",
        json={
            "original_url": "https://expired-redirect.example.com",
            "expires_at": "2000-01-01T00:00:00Z",
        },
    )
    code = resp.json()["short_code"]


    from tests.conftest import _fake_redis
    await _fake_redis.delete(f"redirect:{code}")

    redirect = await client.get(f"/{code}", follow_redirects=False)
    assert redirect.status_code == 404


@pytest.mark.asyncio
async def test_stats_cached_after_first_call(client: AsyncClient):
    resp = await client.post(
        "/api/v1/links/shorten",
        json={"original_url": "https://cache-test.example.com"},
    )
    code = resp.json()["short_code"]

    stats1 = await client.get(f"/api/v1/links/{code}/stats")
    assert stats1.status_code == 200

    stats2 = await client.get(f"/api/v1/links/{code}/stats")
    assert stats2.status_code == 200
    assert stats1.json()["short_code"] == stats2.json()["short_code"]


@pytest.mark.asyncio
async def test_stats_invalidated_after_delete(client: AsyncClient):
    headers = await register_and_login(client, "cache_delete_user")
    resp = await client.post(
        "/api/v1/links/shorten",
        json={"original_url": "https://cache-delete.example.com"},
        headers=headers,
    )
    code = resp.json()["short_code"]

    await client.get(f"/api/v1/links/{code}/stats")

    await client.delete(f"/api/v1/links/{code}", headers=headers)

    stats = await client.get(f"/api/v1/links/{code}/stats")
    assert stats.status_code == 404


@pytest.mark.asyncio
async def test_redirect_cache_invalidated_after_update(client: AsyncClient):
    headers = await register_and_login(client, "cache_update_user")
    resp = await client.post(
        "/api/v1/links/shorten",
        json={"original_url": "https://old-cached.example.com"},
        headers=headers,
    )
    code = resp.json()["short_code"]

    await client.get(f"/{code}", follow_redirects=False)

    await client.put(
        f"/api/v1/links/{code}",
        json={"original_url": "https://new-cached.example.com"},
        headers=headers,
    )

    redirect = await client.get(f"/{code}", follow_redirects=False)
    assert redirect.headers["location"] == "https://new-cached.example.com"


@pytest.mark.asyncio
async def test_multiple_redirects_count(client: AsyncClient):
    resp = await client.post(
        "/api/v1/links/shorten",
        json={"original_url": "https://multi-click.example.com"},
    )
    code = resp.json()["short_code"]

    for _ in range(5):
        await client.get(f"/{code}", follow_redirects=False)

    stats = await client.get(f"/api/v1/links/{code}/stats")
    assert stats.json()["click_count"] == 5
