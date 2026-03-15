"""Unit tests for LinkService — tests business logic in isolation."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.link_service import LinkService, generate_short_code
from app.schemas.schemas import LinkCreate, LinkUpdate
from tests.conftest import TestSessionLocal


def utcnow():
    return datetime.now(timezone.utc)



def test_generate_short_code_default_length():
    code = generate_short_code()
    assert len(code) == 7


def test_generate_short_code_custom_length():
    code = generate_short_code(12)
    assert len(code) == 12


def test_generate_short_code_alphanumeric():
    for _ in range(50):
        code = generate_short_code()
        assert code.isalnum(), f"Non-alphanumeric code: {code}"


def test_generate_short_code_uniqueness():
    codes = {generate_short_code() for _ in range(200)}
    assert len(codes) == 200



@pytest.mark.asyncio
async def test_create_link_no_owner():
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch("app.core.cache.cache_set", new_callable=AsyncMock):
            link = await svc.create(
                LinkCreate(original_url="https://unit.example.com"),
                owner=None,
            )
            await db.commit()

        assert link.owner_id is None
        assert link.short_code
        assert link.original_url == "https://unit.example.com"


@pytest.mark.asyncio
async def test_create_link_custom_alias():
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch("app.core.cache.cache_set", new_callable=AsyncMock):
            link = await svc.create(
                LinkCreate(original_url="https://alias-unit.example.com", custom_alias="unitalias"),
                owner=None,
            )
            await db.commit()

        assert link.short_code == "unitalias"


@pytest.mark.asyncio
async def test_create_duplicate_alias_raises():
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch("app.core.cache.cache_set", new_callable=AsyncMock):
            await svc.create(
                LinkCreate(original_url="https://first-unit.example.com", custom_alias="dupunit"),
                owner=None,
            )
            await db.commit()

        with pytest.raises(ValueError, match="already taken"):
            with patch("app.core.cache.cache_set", new_callable=AsyncMock):
                await svc.create(
                    LinkCreate(original_url="https://second-unit.example.com", custom_alias="dupunit"),
                    owner=None,
                )


@pytest.mark.asyncio
async def test_expire_old_links():
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        past = utcnow() - timedelta(seconds=1)
        with patch("app.core.cache.cache_set", new_callable=AsyncMock), \
             patch("app.core.cache.cache_delete", new_callable=AsyncMock):
            link = await svc.create(
                LinkCreate(original_url="https://expiring-unit.example.com", expires_at=past),
                owner=None,
            )
            await db.commit()

            count = await svc.expire_old_links()
            await db.commit()

        assert count >= 1


@pytest.mark.asyncio
async def test_search_by_url_returns_matches():
    target = "https://search-unit.example.com/unique-path"
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch("app.core.cache.cache_set", new_callable=AsyncMock), \
             patch("app.core.cache.cache_get", return_value=None):
            await svc.create(LinkCreate(original_url=target, custom_alias="su1"), owner=None)
            await svc.create(LinkCreate(original_url=target, custom_alias="su2"), owner=None)
            await db.commit()

            results = await svc.search_by_url(target)

        codes = [r["short_code"] for r in results]
        assert "su1" in codes
        assert "su2" in codes



@pytest.mark.asyncio
async def test_unique_code_exhaustion():
    """_unique_code должен поднять RuntimeError если все 10 попыток заняты."""
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch.object(svc, "_code_exists", new=AsyncMock(return_value=True)):
            with pytest.raises(RuntimeError, match="Could not generate unique short code"):
                await svc._unique_code()


@pytest.mark.asyncio
async def test_get_redirect_popular_link_uses_popular_ttl():
    """get_redirect должен использовать POPULAR_LINK_TTL когда click_count >= POPULAR_THRESHOLD."""
    from unittest.mock import MagicMock
    from app.core.config import settings

    async with TestSessionLocal() as db:
        svc = LinkService(db)

        mock_link = MagicMock()
        mock_link.click_count = settings.POPULAR_THRESHOLD  
        mock_link.original_url = "https://popular-unit.example.com"
        mock_link.short_code = "popularunit"

        with patch("app.services.link_service.cache_get", AsyncMock(return_value=None)), \
             patch("app.services.link_service.cache_set", new_callable=AsyncMock) as mock_set, \
             patch.object(svc, "_get_active", AsyncMock(return_value=mock_link)), \
             patch.object(svc, "_record_click", AsyncMock()):

            result = await svc.get_redirect("popularunit")

        assert result == "https://popular-unit.example.com"
        mock_set.assert_called_once()
        _, call_kwargs = mock_set.call_args
        assert call_kwargs["ttl"] == settings.POPULAR_LINK_TTL


@pytest.mark.asyncio
async def test_get_redirect_cache_hit():
    """get_redirect должен возвращать URL из кэша и не лезть в БД."""
    async with TestSessionLocal() as db:
        svc = LinkService(db)

        cached_url = "https://cached-url.example.com"
        with patch("app.services.link_service.cache_get", AsyncMock(return_value=cached_url)), \
             patch.object(svc, "_get_active", AsyncMock()) as mock_db, \
             patch.object(svc, "_record_click", AsyncMock()):

            result = await svc.get_redirect("cachedcode")

        assert result == cached_url
        mock_db.assert_not_called()


@pytest.mark.asyncio
async def test_get_redirect_not_found():
    """get_redirect должен вернуть None если ссылка не найдена."""
    async with TestSessionLocal() as db:
        svc = LinkService(db)

        with patch("app.services.link_service.cache_get", AsyncMock(return_value=None)), \
             patch.object(svc, "_get_active", AsyncMock(return_value=None)):

            result = await svc.get_redirect("doesnotexist")

        assert result is None


@pytest.mark.asyncio
async def test_get_expired_history_unit():
    """get_expired_history должен вернуть мягко удалённые ссылки."""
    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch("app.core.cache.cache_set", new_callable=AsyncMock), \
             patch("app.core.cache.cache_delete", new_callable=AsyncMock):
            link = await svc.create(
                LinkCreate(original_url="https://history-unit.example.com", custom_alias="histunit"),
                owner=None,
            )
            await db.commit()

            from app.models.models import User
            fake_owner = MagicMock(spec=User)
            fake_owner.id = link.owner_id  

        with patch("app.core.cache.cache_delete", new_callable=AsyncMock):
            from sqlalchemy import update
            from app.models.models import Link as LinkModel
            await db.execute(
                update(LinkModel)
                .where(LinkModel.short_code == "histunit")
                .values(is_active=False)
            )
            await db.commit()

            history = await svc.get_expired_history()

        codes = [l.short_code for l in history]
        assert "histunit" in codes


@pytest.mark.asyncio
async def test_cleanup_unused_last_used_at_none():
    """cleanup_unused должен удалять ссылки никогда не использованные, если они старые."""
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import update
    from app.models.models import Link as LinkModel

    async with TestSessionLocal() as db:
        svc = LinkService(db)
        with patch("app.core.cache.cache_set", new_callable=AsyncMock), \
             patch("app.core.cache.cache_delete", new_callable=AsyncMock):
            link = await svc.create(
                LinkCreate(
                    original_url="https://never-used.example.com",
                    custom_alias="neverused1",
                ),
                owner=None,
            )
            await db.commit()

            old_date = datetime.now(timezone.utc) - timedelta(days=100)
            await db.execute(
                update(LinkModel)
                .where(LinkModel.short_code == "neverused1")
                .values(created_at=old_date, last_used_at=None)
            )
            await db.commit()

            count = await svc.cleanup_unused(ttl_days=30)
            await db.commit()

        assert count >= 1
