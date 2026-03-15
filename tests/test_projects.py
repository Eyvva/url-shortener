import pytest
from httpx import AsyncClient
from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    headers = await register_and_login(client, "proj_creator")
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "My Project", "description": "Test project"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Project"
    assert body["description"] == "Test project"
    assert body["link_count"] == 0


@pytest.mark.asyncio
async def test_create_project_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "Unauth"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    headers = await register_and_login(client, "proj_lister")
    await client.post("/api/v1/projects", json={"name": "P1"}, headers=headers)
    await client.post("/api/v1/projects", json={"name": "P2"}, headers=headers)

    resp = await client.get("/api/v1/projects", headers=headers)
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "P1" in names
    assert "P2" in names


@pytest.mark.asyncio
async def test_list_projects_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient):
    headers = await register_and_login(client, "proj_deleter")
    create = await client.post("/api/v1/projects", json={"name": "ToDelete"}, headers=headers)
    pid = create.json()["id"]

    resp = await client.delete(f"/api/v1/projects/{pid}", headers=headers)
    assert resp.status_code == 200

    projects = await client.get("/api/v1/projects", headers=headers)
    ids = [p["id"] for p in projects.json()]
    assert pid not in ids


@pytest.mark.asyncio
async def test_delete_project_not_found(client: AsyncClient):
    headers = await register_and_login(client, "proj_del_nf")
    resp = await client.delete("/api/v1/projects/999999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_project_link_count(client: AsyncClient):
    headers = await register_and_login(client, "proj_count_user")
    proj = await client.post("/api/v1/projects", json={"name": "Counted"}, headers=headers)
    pid = proj.json()["id"]

    await client.post(
        "/api/v1/links/shorten",
        json={"original_url": "https://project-link.example.com", "project_id": pid},
        headers=headers,
    )

    resp = await client.get("/api/v1/projects", headers=headers)
    project = next(p for p in resp.json() if p["id"] == pid)
    assert project["link_count"] == 1
