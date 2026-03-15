from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import (
    cache_get, cache_set, cache_delete,
    redirect_key, stats_key, search_key,
)
from app.core.config import settings
from app.models.models import Link, User
from app.schemas.schemas import LinkCreate, LinkUpdate


ALPHABET = string.ascii_letters + string.digits


def generate_short_code(length: int = settings.SHORT_CODE_LENGTH) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LinkService:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def _get_active(self, short_code: str) -> Optional[Link]:
        result = await self.db.execute(
            select(Link).where(
                Link.short_code == short_code,
                Link.is_active == True,
                or_(Link.expires_at == None, Link.expires_at > utcnow()),
            )
        )
        return result.scalar_one_or_none()

    async def _code_exists(self, code: str) -> bool:
        result = await self.db.execute(
            select(Link.id).where(Link.short_code == code)
        )
        return result.scalar_one_or_none() is not None

    async def _unique_code(self) -> str:
        for _ in range(10):
            code = generate_short_code()
            if not await self._code_exists(code):
                return code
        raise RuntimeError("Could not generate unique short code after 10 attempts")

    def _build_short_url(self, short_code: str) -> str:
        return f"{settings.BASE_URL}/{short_code}"


    async def create(self, data: LinkCreate, owner: Optional[User]) -> Link:
        short_code = data.custom_alias or await self._unique_code()

        if await self._code_exists(short_code):
            raise ValueError(f"Alias '{short_code}' is already taken")

        link = Link(
            short_code=short_code,
            original_url=str(data.original_url),
            owner_id=owner.id if owner else None,
            project_id=data.project_id,
            expires_at=data.expires_at,
        )
        self.db.add(link)
        await self.db.flush()
        await self.db.refresh(link)

        await cache_set(
            redirect_key(short_code),
            link.original_url,
            ttl=settings.REDIRECT_CACHE_TTL,
        )
        return link

    async def get_redirect(self, short_code: str) -> Optional[str]:
        """Returns original URL (with caching) and increments click count."""
        rkey = redirect_key(short_code)

        cached = await cache_get(rkey)
        if cached:
            await self._record_click(short_code)
            return cached

        link = await self._get_active(short_code)
        if not link:
            return None

        await self._record_click(short_code, link)

        ttl = (
            settings.POPULAR_LINK_TTL
            if link.click_count >= settings.POPULAR_THRESHOLD
            else settings.REDIRECT_CACHE_TTL
        )
        await cache_set(rkey, link.original_url, ttl=ttl)
        return link.original_url

    async def _record_click(self, short_code: str, link: Optional[Link] = None) -> None:
        now = utcnow()
        await self.db.execute(
            update(Link)
            .where(Link.short_code == short_code)
            .values(
                click_count=Link.click_count + 1,
                last_used_at=now,
            )
        )
        await cache_delete(stats_key(short_code))

    async def get_stats(self, short_code: str) -> Optional[Link]:
        skey = stats_key(short_code)
        cached = await cache_get(skey)
        if cached:
            return cached  

        link = await self._get_active(short_code)
        if not link:
            return None

        payload = {
            "short_code": link.short_code,
            "original_url": link.original_url,
            "short_url": self._build_short_url(link.short_code),
            "click_count": link.click_count,
            "created_at": link.created_at.isoformat(),
            "last_used_at": link.last_used_at.isoformat() if link.last_used_at else None,
            "expires_at": link.expires_at.isoformat() if link.expires_at else None,
            "owner_id": link.owner_id,
            "project_id": link.project_id,
        }
        await cache_set(skey, payload, ttl=settings.CACHE_TTL)
        return payload

    async def update(self, short_code: str, data: LinkUpdate, owner: User) -> Optional[Link]:
        link = await self._get_active(short_code)
        if not link:
            return None
        if link.owner_id != owner.id:
            raise PermissionError("Not the owner of this link")

        new_code = short_code
        if data.short_code and data.short_code != short_code:
            if await self._code_exists(data.short_code):
                raise ValueError(f"Short code '{data.short_code}' is already taken")
            new_code = data.short_code

        values: dict = {}
        if data.original_url:
            values["original_url"] = str(data.original_url)
        if new_code != short_code:
            values["short_code"] = new_code
        if data.expires_at is not None:
            values["expires_at"] = data.expires_at
        if data.project_id is not None:
            values["project_id"] = data.project_id

        if values:
            await self.db.execute(
                update(Link).where(Link.short_code == short_code).values(**values)
            )

        await cache_delete(redirect_key(short_code), stats_key(short_code))
        if link.original_url:
            await cache_delete(search_key(link.original_url))

        await self.db.flush()
        return await self._get_active(new_code)

    async def delete(self, short_code: str, owner: User) -> bool:
        link = await self._get_active(short_code)
        if not link:
            return False
        if link.owner_id != owner.id:
            raise PermissionError("Not the owner of this link")

        now = utcnow()
        await self.db.execute(
            update(Link)
            .where(Link.short_code == short_code)
            .values(is_active=False, deleted_at=now)
        )

        await cache_delete(redirect_key(short_code), stats_key(short_code))
        if link.original_url:
            await cache_delete(search_key(link.original_url))
        return True


    async def search_by_url(self, original_url: str) -> List[Link]:
        skey = search_key(original_url)
        cached = await cache_get(skey)
        if cached:
            return cached  

        result = await self.db.execute(
            select(Link).where(
                Link.original_url == original_url,
                Link.is_active == True,
                or_(Link.expires_at == None, Link.expires_at > utcnow()),
            )
        )
        links = result.scalars().all()

        payload = [
            {
                "id": l.id,
                "short_code": l.short_code,
                "original_url": l.original_url,
                "short_url": self._build_short_url(l.short_code),
                "owner_id": l.owner_id,
                "project_id": l.project_id,
                "click_count": l.click_count,
                "created_at": l.created_at.isoformat(),
                "last_used_at": l.last_used_at.isoformat() if l.last_used_at else None,
                "expires_at": l.expires_at.isoformat() if l.expires_at else None,
                "is_active": l.is_active,
            }
            for l in links
        ]
        await cache_set(skey, payload, ttl=settings.CACHE_TTL)
        return payload

    async def expire_old_links(self) -> int:
        """Soft-delete links whose expires_at has passed."""
        now = utcnow()
        result = await self.db.execute(
            select(Link).where(
                Link.is_active == True,
                Link.expires_at != None,
                Link.expires_at <= now,
            )
        )
        links = result.scalars().all()
        count = 0
        for link in links:
            await self.db.execute(
                update(Link)
                .where(Link.id == link.id)
                .values(is_active=False, deleted_at=now)
            )
            await cache_delete(redirect_key(link.short_code), stats_key(link.short_code))
            count += 1
        return count

    async def cleanup_unused(self, ttl_days: int) -> int:
        """Soft-delete links not used for `ttl_days` days."""
        cutoff = utcnow() - timedelta(days=ttl_days)
        result = await self.db.execute(
            select(Link).where(
                Link.is_active == True,
                or_(
                    and_(Link.last_used_at != None, Link.last_used_at < cutoff),
                    and_(Link.last_used_at == None, Link.created_at < cutoff),
                ),
            )
        )
        links = result.scalars().all()
        now = utcnow()
        count = 0
        for link in links:
            await self.db.execute(
                update(Link)
                .where(Link.id == link.id)
                .values(is_active=False, deleted_at=now)
            )
            await cache_delete(redirect_key(link.short_code), stats_key(link.short_code))
            count += 1
        return count

    async def get_expired_history(self) -> List[Link]:
        """Return all soft-deleted (expired/cleaned) links for history."""
        result = await self.db.execute(
            select(Link).where(Link.is_active == False).order_by(Link.deleted_at.desc())
        )
        return result.scalars().all()
