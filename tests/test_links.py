import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login



async def _shorten(client: AsyncClient, url: str, headers: dict = None, **kwargs) -> dict:
    payload = {"original_url": url, **kwargs}
    resp = await client.post("/api/v1/links/shorten", json=payload, headers=headers or {})
    return resp



@pytest.mark.asyncio
async def test_shorten_anonymous(client: AsyncClient):
    resp = await _shorten(client, "https://www.example.com/some/long/path")
    assert resp.status_code == 201
    body = resp.json()
    assert "short_code" in body
    assert body["original_url"] == "https://www.example.com/some/long/path"
    assert body["short_url"].endswith(body["short_code"])
    assert body["owner_id"] is None


@pytest.mark.asyncio
async def test_shorten_authenticated(client: AsyncClient):
    headers = await register_and_login(client, "user_shorten")
    resp = await _shorten(client, "https://authenticated.example.com", headers=headers)
    assert resp.status_code == 201
    assert resp.json()["owner_id"] is not None


@pytest.mark.asyncio
async def test_shorten_custom_alias(client: AsyncClient):
    resp = await _shorten(client, "https://alias.example.com", custom_alias="myalias")
    assert resp.status_code == 201
    assert resp.json()["short_code"] == "myalias"


@pytest.mark.asyncio
async def test_shorten_duplicate_alias(client: AsyncClient):
    await _shorten(client, "https://first.example.com", custom_alias="dupalias")
    resp = await _shorten(client, "https://second.example.com", custom_alias="dupalias")
    assert resp.status_code == 409
    assert "already taken" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_shorten_invalid_url(client: AsyncClient):
    resp = await _shorten(client, "not-a-url")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_shorten_with_expiry(client: AsyncClient):
    resp = await _shorten(
        client,
        "https://expiring.example.com",
        expires_at="2099-12-31T23:59:00Z",
    )
    assert resp.status_code == 201
    assert resp.json()["expires_at"] is not None



@pytest.mark.asyncio
async def test_redirect_success(client: AsyncClient):
    create = await _shorten(client, "https://redirect-target.example.com")
    code = create.json()["short_code"]

    resp = await client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://redirect-target.example.com"


@pytest.mark.asyncio
async def test_redirect_increments_click_count(client: AsyncClient):
    create = await _shorten(client, "https://click-count.example.com")
    code = create.json()["short_code"]

    await client.get(f"/{code}", follow_redirects=False)
    await client.get(f"/{code}", follow_redirects=False)

    stats = await client.get(f"/api/v1/links/{code}/stats")
    assert stats.json()["click_count"] == 2


@pytest.mark.asyncio
async def test_redirect_not_found(client: AsyncClient):
    resp = await client.get("/nonexistentcode123", follow_redirects=False)
    assert resp.status_code == 404



@pytest.mark.asyncio
async def test_stats_success(client: AsyncClient):
    create = await _shorten(client, "https://stats.example.com")
    code = create.json()["short_code"]

    resp = await client.get(f"/api/v1/links/{code}/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["short_code"] == code
    assert body["original_url"] == "https://stats.example.com"
    assert "click_count" in body
    assert "created_at" in body
    assert "last_used_at" in body


@pytest.mark.asyncio
async def test_stats_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/links/doesnotexist/stats")
    assert resp.status_code == 404



@pytest.mark.asyncio
async def test_update_requires_auth(client: AsyncClient):
    create = await _shorten(client, "https://update-no-auth.example.com")
    code = create.json()["short_code"]
    resp = await client.put(f"/api/v1/links/{code}", json={"original_url": "https://new.example.com"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_original_url(client: AsyncClient):
    headers = await register_and_login(client, "user_update")
    create = await _shorten(client, "https://old-url.example.com", headers=headers)
    code = create.json()["short_code"]

    resp = await client.put(
        f"/api/v1/links/{code}",
        json={"original_url": "https://new-url.example.com"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["original_url"] == "https://new-url.example.com"


@pytest.mark.asyncio
async def test_update_short_code(client: AsyncClient):
    headers = await register_and_login(client, "user_update_code")
    create = await _shorten(client, "https://rename.example.com", headers=headers)
    old_code = create.json()["short_code"]

    resp = await client.put(
        f"/api/v1/links/{old_code}",
        json={"short_code": "brandnewcode"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["short_code"] == "brandnewcode"


@pytest.mark.asyncio
async def test_update_forbidden_for_other_user(client: AsyncClient):
    headers_a = await register_and_login(client, "owner_user")
    headers_b = await register_and_login(client, "other_user")

    create = await _shorten(client, "https://owned.example.com", headers=headers_a)
    code = create.json()["short_code"]

    resp = await client.put(
        f"/api/v1/links/{code}",
        json={"original_url": "https://hacked.example.com"},
        headers=headers_b,
    )
    assert resp.status_code == 403



@pytest.mark.asyncio
async def test_delete_requires_auth(client: AsyncClient):
    create = await _shorten(client, "https://delete-no-auth.example.com")
    code = create.json()["short_code"]
    resp = await client.delete(f"/api/v1/links/{code}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_success(client: AsyncClient):
    headers = await register_and_login(client, "user_delete")
    create = await _shorten(client, "https://to-delete.example.com", headers=headers)
    code = create.json()["short_code"]

    resp = await client.delete(f"/api/v1/links/{code}", headers=headers)
    assert resp.status_code == 200
    assert "deleted" in resp.json()["message"]

    redirect = await client.get(f"/{code}", follow_redirects=False)
    assert redirect.status_code == 404


@pytest.mark.asyncio
async def test_delete_forbidden_for_other_user(client: AsyncClient):
    headers_a = await register_and_login(client, "del_owner")
    headers_b = await register_and_login(client, "del_other")

    create = await _shorten(client, "https://del-owned.example.com", headers=headers_a)
    code = create.json()["short_code"]

    resp = await client.delete(f"/api/v1/links/{code}", headers=headers_b)
    assert resp.status_code == 403



@pytest.mark.asyncio
async def test_search_by_url(client: AsyncClient):
    target = "https://searchable.example.com"
    await _shorten(client, target, custom_alias="search1")
    await _shorten(client, target, custom_alias="search2")

    resp = await client.get(f"/api/v1/links/search?original_url={target}")
    assert resp.status_code == 200
    codes = [item["short_code"] for item in resp.json()]
    assert "search1" in codes
    assert "search2" in codes


@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient):
    resp = await client.get("/api/v1/links/search?original_url=https://nomatch.example.com")
    assert resp.status_code == 200
    assert resp.json() == []



@pytest.mark.asyncio
async def test_expired_history_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/links/expired")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_history_returns_deleted(client: AsyncClient):
    headers = await register_and_login(client, "user_expired")
    create = await _shorten(client, "https://will-be-deleted.example.com", headers=headers)
    code = create.json()["short_code"]

    await client.delete(f"/api/v1/links/{code}", headers=headers)

    resp = await client.get("/api/v1/links/expired", headers=headers)
    assert resp.status_code == 200
    codes = [item["short_code"] for item in resp.json()]
    assert code in codes



@pytest.mark.asyncio
async def test_cleanup_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/links/cleanup", json={"days": 7})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cleanup_success(client: AsyncClient):
    headers = await register_and_login(client, "user_cleanup")
    resp = await client.post("/api/v1/links/cleanup", json={"days": 9999}, headers=headers)
    assert resp.status_code == 200
    assert "Cleaned up" in resp.json()["message"]
