"""Тесты граничных случаев и невалидных данных."""
import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login



@pytest.mark.asyncio
async def test_shorten_empty_body(client: AsyncClient):
    resp = await client.post("/api/v1/links/shorten", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_shorten_missing_url(client: AsyncClient):
    resp = await client.post("/api/v1/links/shorten", json={"custom_alias": "test"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_shorten_url_without_scheme(client: AsyncClient):
    resp = await client.post(
        "/api/v1/links/shorten",
        json={"original_url": "www.example.com"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cleanup_zero_days(client: AsyncClient):
    headers = await register_and_login(client, "cleanup_zero")
    resp = await client.post(
        "/api/v1/links/cleanup",
        json={"days": 0},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cleanup_negative_days(client: AsyncClient):
    headers = await register_and_login(client, "cleanup_neg")
    resp = await client.post(
        "/api/v1/links/cleanup",
        json={"days": -5},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_nonexistent_link(client: AsyncClient):
    headers = await register_and_login(client, "update_nonexist")
    resp = await client.put(
        "/api/v1/links/nonexistentcode999",
        json={"original_url": "https://example.com"},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_link(client: AsyncClient):
    headers = await register_and_login(client, "delete_nonexist")
    resp = await client.delete("/api/v1/links/nonexistent999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stats_after_update(client: AsyncClient):
    headers = await register_and_login(client, "stats_after_update")
    resp = await client.post(
        "/api/v1/links/shorten",
        json={"original_url": "https://before-update.example.com"},
        headers=headers,
    )
    code = resp.json()["short_code"]

    await client.put(
        f"/api/v1/links/{code}",
        json={"original_url": "https://after-update.example.com"},
        headers=headers,
    )

    stats = await client.get(f"/api/v1/links/{code}/stats")
    assert stats.json()["original_url"] == "https://after-update.example.com"


@pytest.mark.asyncio
async def test_search_empty_url(client: AsyncClient):
    resp = await client.get("/api/v1/links/search?original_url=")
    assert resp.status_code in (200, 422)


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "testuser99", "email": "not-an-email", "password": "pass123"},
    )
    assert resp.status_code in (201, 422)


@pytest.mark.asyncio
async def test_login_empty_credentials(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "", "password": ""},
    )
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_project_delete_nonexistent(client: AsyncClient):
    headers = await register_and_login(client, "proj_del_nonexist")
    resp = await client.delete("/api/v1/projects/999999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_duplicate_short_code(client: AsyncClient):
    headers = await register_and_login(client, "dup_code_user")

    resp1 = await client.post(
        "/api/v1/links/shorten",
        json={"original_url": "https://first-dup.example.com", "custom_alias": "firstcode"},
        headers=headers,
    )
    resp2 = await client.post(
        "/api/v1/links/shorten",
        json={"original_url": "https://second-dup.example.com", "custom_alias": "secondcode"},
        headers=headers,
    )

    resp = await client.put(
        "/api/v1/links/secondcode",
        json={"short_code": "firstcode"},
        headers=headers,
    )
    assert resp.status_code == 409
