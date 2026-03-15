"""
Прямые unit-тесты сервисного слоя через TestSessionLocal.
Покрывают код, который coverage не отслеживает через ASGI transport.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import update

from app.models.models import Link as LinkModel, User, Project
from app.schemas.schemas import (
    UserRegister, ProjectCreate, LinkCreate, LinkUpdate,
)
from app.services.user_service import UserService
from app.services.project_service import ProjectService
from app.services.link_service import LinkService
from tests.conftest import TestSessionLocal



@pytest.mark.asyncio
async def test_user_service_create_and_get_by_id():
    async with TestSessionLocal() as db:
        svc = UserService(db)
        user = await svc.create(UserRegister(username="usvc1", email="usvc1@test.com", password="pass"))
        await db.commit()

        fetched = await svc.get_by_id(user.id)
        assert fetched is not None
        assert fetched.username == "usvc1"


@pytest.mark.asyncio
async def test_user_service_get_by_username():
    async with TestSessionLocal() as db:
        svc = UserService(db)
        await svc.create(UserRegister(username="usvc2", email="usvc2@test.com", password="pass"))
        await db.commit()

        found = await svc.get_by_username("usvc2")
        assert found is not None
        assert found.email == "usvc2@test.com"


@pytest.mark.asyncio
async def test_user_service_get_by_email():
    async with TestSessionLocal() as db:
        svc = UserService(db)
        await svc.create(UserRegister(username="usvc3", email="usvc3@test.com", password="pass"))
        await db.commit()

        found = await svc.get_by_email("usvc3@test.com")
        assert found is not None
        assert found.username == "usvc3"


@pytest.mark.asyncio
async def test_user_service_get_by_id_not_found():
    async with TestSessionLocal() as db:
        svc = UserService(db)
        result = await svc.get_by_id(999999)
        assert result is None


@pytest.mark.asyncio
async def test_user_service_authenticate_success():
    async with TestSessionLocal() as db:
        svc = UserService(db)
        await svc.create(UserRegister(username="usvc4", email="usvc4@test.com", password="mypassword"))
        await db.commit()

        user = await svc.authenticate("usvc4", "mypassword")
        assert user is not None
        assert user.username == "usvc4"


@pytest.mark.asyncio
async def test_user_service_authenticate_wrong_password():
    async with TestSessionLocal() as db:
        svc = UserService(db)
        await svc.create(UserRegister(username="usvc5", email="usvc5@test.com", password="correctpass"))
        await db.commit()

        result = await svc.authenticate("usvc5", "wrongpass")
        assert result is None



async def _make_user(db, username: str) -> User:
    svc = UserService(db)
    user = await svc.create(UserRegister(username=username, email=f"{username}@test.com", password="pass"))
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_project_service_create_and_list():
    async with TestSessionLocal() as db:
        user = await _make_user(db, "psvc1")
        svc = ProjectService(db)

        proj = await svc.create(ProjectCreate(name="TestProj", description="Desc"), owner=user)
        await db.commit()

        assert proj.name == "TestProj"
        assert proj.owner_id == user.id

        projects = await svc.list_for_user(owner=user)
        assert any(p.id == proj.id for p in projects)


@pytest.mark.asyncio
async def test_project_service_get():
    async with TestSessionLocal() as db:
        user = await _make_user(db, "psvc2")
        svc = ProjectService(db)

        proj = await svc.create(ProjectCreate(name="GetProj"), owner=user)
        await db.commit()

        fetched = await svc.get(proj.id, owner=user)
        assert fetched is not None
        assert fetched.name == "GetProj"

        not_found = await svc.get(999999, owner=user)
        assert not_found is None


@pytest.mark.asyncio
async def test_project_service_delete():
    async with TestSessionLocal() as db:
        user = await _make_user(db, "psvc3")
        svc = ProjectService(db)

        proj = await svc.create(ProjectCreate(name="ToDelete"), owner=user)
        await db.commit()

        deleted = await svc.delete(proj.id, owner=user)
        assert deleted is True
        await db.flush()

        not_found = await svc.get(proj.id, owner=user)
        assert not_found is None


@pytest.mark.asyncio
async def test_project_service_delete_not_found():
    async with TestSessionLocal() as db:
        user = await _make_user(db, "psvc4")
        svc = ProjectService(db)

        result = await svc.delete(999999, owner=user)
        assert result is False


@pytest.mark.asyncio
async def test_project_service_get_link_count():
    async with TestSessionLocal() as db:
        user = await _make_user(db, "psvc5")
        proj_svc = ProjectService(db)
        link_svc = LinkService(db)

        proj = await proj_svc.create(ProjectCreate(name="WithLinks"), owner=user)
        await db.flush()

        with patch("app.core.cache.cache_set", AsyncMock()):
            await link_svc.create(
                LinkCreate(
                    original_url="https://proj-link.example.com",
                    custom_alias="psvclink1",
                    project_id=proj.id,
                ),
                owner=user,
            )
            await db.flush()

        count = await proj_svc.get_link_count(proj.id)
        assert count == 1



@pytest.mark.asyncio
async def test_link_service_get_stats_unit():
    """get_stats: путь через БД (без кэша)."""
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch("app.core.cache.cache_set", AsyncMock()), \
             patch("app.services.link_service.cache_get", AsyncMock(return_value=None)):
            await svc.create(
                LinkCreate(original_url="https://stats-direct.example.com", custom_alias="statsdirect"),
                owner=None,
            )
            await db.commit()

            result = await svc.get_stats("statsdirect")

    assert result is not None
    assert result["short_code"] == "statsdirect"
    assert result["original_url"] == "https://stats-direct.example.com"
    assert result["click_count"] == 0


@pytest.mark.asyncio
async def test_link_service_get_stats_cache_hit():
    """get_stats: путь через кэш."""
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        cached_payload = {
            "short_code": "cachedstats",
            "original_url": "https://cached-stats.example.com",
        }
        with patch("app.services.link_service.cache_get", AsyncMock(return_value=cached_payload)):
            result = await svc.get_stats("cachedstats")

    assert result == cached_payload


@pytest.mark.asyncio
async def test_link_service_get_stats_not_found():
    """get_stats: ссылка не найдена."""
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch("app.services.link_service.cache_get", AsyncMock(return_value=None)):
            result = await svc.get_stats("nonexistent999")

    assert result is None


@pytest.mark.asyncio
async def test_link_service_record_click_unit():
    """_record_click: обновляет click_count и сбрасывает кэш."""
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch("app.core.cache.cache_set", AsyncMock()), \
             patch("app.services.link_service.cache_delete", AsyncMock()) as mock_del:
            await svc.create(
                LinkCreate(original_url="https://rclick-direct.example.com", custom_alias="rclickdirect"),
                owner=None,
            )
            await db.commit()

            await svc._record_click("rclickdirect")
            await db.commit()
            mock_del.assert_called()


@pytest.mark.asyncio
async def test_link_service_update_unit():
    """update: изменяет URL, очищает кэш."""
    async with TestSessionLocal() as db:
        user = await _make_user(db, "updunit1")
        svc = LinkService(db)

        with patch("app.core.cache.cache_set", AsyncMock()), \
             patch("app.services.link_service.cache_delete", AsyncMock()):
            await svc.create(
                LinkCreate(original_url="https://before-upd.example.com", custom_alias="upd1"),
                owner=user,
            )
            await db.commit()

            updated = await svc.update(
                "upd1",
                LinkUpdate(original_url="https://after-upd.example.com"),
                owner=user,
            )
            await db.commit()

    assert updated is not None
    assert updated.original_url == "https://after-upd.example.com"


@pytest.mark.asyncio
async def test_link_service_update_permission_error():
    """update: PermissionError если не владелец."""
    async with TestSessionLocal() as db:
        owner = await _make_user(db, "updowner1")
        other = await _make_user(db, "updother1")
        svc = LinkService(db)

        with patch("app.core.cache.cache_set", AsyncMock()):
            await svc.create(
                LinkCreate(original_url="https://owned-upd.example.com", custom_alias="ownedupd1"),
                owner=owner,
            )
            await db.commit()

        with pytest.raises(PermissionError):
            with patch("app.services.link_service.cache_delete", AsyncMock()):
                await svc.update(
                    "ownedupd1",
                    LinkUpdate(original_url="https://hacked.example.com"),
                    owner=other,
                )


@pytest.mark.asyncio
async def test_link_service_update_not_found():
    """update: возвращает None если ссылка не найдена."""
    async with TestSessionLocal() as db:
        user = await _make_user(db, "updnf1")
        svc = LinkService(db)

        result = await svc.update(
            "nonexistentupdnf",
            LinkUpdate(original_url="https://nope.example.com"),
            owner=user,
        )

    assert result is None


@pytest.mark.asyncio
async def test_link_service_update_duplicate_code():
    """update: ValueError если новый код уже занят."""
    async with TestSessionLocal() as db:
        user = await _make_user(db, "dupcodeupd1")
        svc = LinkService(db)

        with patch("app.core.cache.cache_set", AsyncMock()):
            await svc.create(
                LinkCreate(original_url="https://first-upd.example.com", custom_alias="firstupd1"),
                owner=user,
            )
            await svc.create(
                LinkCreate(original_url="https://second-upd.example.com", custom_alias="secondupd1"),
                owner=user,
            )
            await db.commit()

        with pytest.raises(ValueError, match="already taken"):
            with patch("app.services.link_service.cache_delete", AsyncMock()):
                await svc.update(
                    "secondupd1",
                    LinkUpdate(short_code="firstupd1"),
                    owner=user,
                )


@pytest.mark.asyncio
async def test_link_service_delete_unit():
    """delete: мягко удаляет ссылку."""
    async with TestSessionLocal() as db:
        user = await _make_user(db, "delunit1")
        svc = LinkService(db)

        with patch("app.core.cache.cache_set", AsyncMock()), \
             patch("app.services.link_service.cache_delete", AsyncMock()):
            await svc.create(
                LinkCreate(original_url="https://del-direct.example.com", custom_alias="deldirect1"),
                owner=user,
            )
            await db.commit()

            deleted = await svc.delete("deldirect1", owner=user)
            await db.commit()

    assert deleted is True


@pytest.mark.asyncio
async def test_link_service_delete_permission_error():
    """delete: PermissionError если не владелец."""
    async with TestSessionLocal() as db:
        owner = await _make_user(db, "delowner1")
        other = await _make_user(db, "delother1")
        svc = LinkService(db)

        with patch("app.core.cache.cache_set", AsyncMock()):
            await svc.create(
                LinkCreate(original_url="https://del-owned.example.com", custom_alias="delowned1"),
                owner=owner,
            )
            await db.commit()

        with pytest.raises(PermissionError):
            with patch("app.services.link_service.cache_delete", AsyncMock()):
                await svc.delete("delowned1", owner=other)


@pytest.mark.asyncio
async def test_link_service_delete_not_found():
    """delete: возвращает False если ссылка не найдена."""
    async with TestSessionLocal() as db:
        user = await _make_user(db, "delnf1")
        svc = LinkService(db)

        result = await svc.delete("doesnotexistdel", owner=user)

    assert result is False


@pytest.mark.asyncio
async def test_link_service_search_by_url_unit():
    """search_by_url: возвращает список ссылок из БД."""
    target = "https://search-direct.example.com"
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch("app.core.cache.cache_set", AsyncMock()), \
             patch("app.services.link_service.cache_get", AsyncMock(return_value=None)):
            await svc.create(LinkCreate(original_url=target, custom_alias="searchd1"), owner=None)
            await svc.create(LinkCreate(original_url=target, custom_alias="searchd2"), owner=None)
            await db.commit()

            results = await svc.search_by_url(target)

    codes = [r["short_code"] for r in results]
    assert "searchd1" in codes
    assert "searchd2" in codes


@pytest.mark.asyncio
async def test_link_service_search_by_url_cache_hit():
    """search_by_url: возвращает кэшированный список."""
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        cached = [{"short_code": "cached_hit", "original_url": "https://x.com"}]
        with patch("app.services.link_service.cache_get", AsyncMock(return_value=cached)):
            result = await svc.search_by_url("https://x.com")

    assert result == cached


@pytest.mark.asyncio
async def test_link_service_get_redirect_non_cached():
    """get_redirect: путь через БД с кэш-миссом."""
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch("app.core.cache.cache_set", AsyncMock()):
            await svc.create(
                LinkCreate(original_url="https://redirect-direct.example.com", custom_alias="reddirect1"),
                owner=None,
            )
            await db.commit()

        with patch("app.services.link_service.cache_get", AsyncMock(return_value=None)), \
             patch("app.services.link_service.cache_set", AsyncMock()):
            result = await svc.get_redirect("reddirect1")
            await db.commit()

    assert result == "https://redirect-direct.example.com"



@pytest.mark.asyncio
async def test_get_db_yields_session_and_commits():
    """get_db: предоставляет сессию и коммитит при успехе."""
    from contextlib import asynccontextmanager
    from app.core.database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()

    @asynccontextmanager
    async def mock_session_maker():
        yield mock_session

    with patch("app.core.database.AsyncSessionLocal", return_value=mock_session_maker()):
        gen = get_db()
        session = await gen.__anext__()
        assert session is mock_session

        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_db_rollback_on_exception():
    """get_db: откатывает транзакцию при исключении."""
    from contextlib import asynccontextmanager
    from app.core.database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()

    @asynccontextmanager
    async def mock_session_maker():
        yield mock_session

    with patch("app.core.database.AsyncSessionLocal", return_value=mock_session_maker()):
        gen = get_db()
        await gen.__anext__()

        with pytest.raises(RuntimeError):
            await gen.athrow(RuntimeError("DB failure"))

    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()
    mock_session.close.assert_called_once()
