from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user_optional, get_current_user_required
from app.models.models import User
from app.schemas.schemas import (
    LinkCreate, LinkOut, LinkStats, LinkUpdate,
    ExpiredLinkOut, MessageOut, UnusedTTLUpdate,
)
from app.services.link_service import LinkService

router = APIRouter(prefix="/links", tags=["Links"])


def _enrich(link_dict: dict) -> dict:
    if "short_url" not in link_dict or not link_dict["short_url"]:
        link_dict["short_url"] = f"{settings.BASE_URL}/{link_dict['short_code']}"
    return link_dict


def _link_to_out(link) -> LinkOut:
    """Convert ORM Link object to LinkOut schema."""
    data = {
        "id": link.id,
        "short_code": link.short_code,
        "original_url": link.original_url,
        "short_url": f"{settings.BASE_URL}/{link.short_code}",
        "owner_id": link.owner_id,
        "project_id": link.project_id,
        "click_count": link.click_count,
        "created_at": link.created_at,
        "last_used_at": link.last_used_at,
        "expires_at": link.expires_at,
        "is_active": link.is_active,
    }
    return LinkOut(**data)




@router.post("/shorten", response_model=LinkOut, status_code=201)
async def shorten(
    data: LinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a short link. Available to all (authenticated and anonymous)."""
    svc = LinkService(db)
    try:
        link = await svc.create(data, owner=current_user)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _link_to_out(link)




@router.get("/search", response_model=List[LinkOut])
async def search(
    original_url: str = Query(..., description="The original URL to look up"),
    db: AsyncSession = Depends(get_db),
):
    """Find all active short links for a given original URL."""
    svc = LinkService(db)
    results = await svc.search_by_url(original_url)
    return [LinkOut(**_enrich(r)) for r in results]




@router.get("/expired", response_model=List[ExpiredLinkOut])
async def expired_history(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user_required),
):
    """(Auth required) History of all expired / deleted links."""
    svc = LinkService(db)
    links = await svc.get_expired_history()
    return [
        ExpiredLinkOut(
            short_code=l.short_code,
            original_url=l.original_url,
            click_count=l.click_count,
            created_at=l.created_at,
            last_used_at=l.last_used_at,
            expires_at=l.expires_at,
            deleted_at=l.deleted_at,
        )
        for l in links
    ]




@router.get("/{short_code}/stats", response_model=LinkStats)
async def stats(short_code: str, db: AsyncSession = Depends(get_db)):
    """Get statistics for a short link. Available to all."""
    svc = LinkService(db)
    result = await svc.get_stats(short_code)
    if not result:
        raise HTTPException(status_code=404, detail="Link not found")
    if isinstance(result, dict):
        return LinkStats(**result)
    return LinkStats(
        short_code=result.short_code,
        original_url=result.original_url,
        short_url=f"{settings.BASE_URL}/{result.short_code}",
        click_count=result.click_count,
        created_at=result.created_at,
        last_used_at=result.last_used_at,
        expires_at=result.expires_at,
        owner_id=result.owner_id,
        project_id=result.project_id,
    )




@router.put("/{short_code}", response_model=LinkOut)
async def update_link(
    short_code: str,
    data: LinkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """(Auth required) Update URL or short code of a link."""
    svc = LinkService(db)
    try:
        link = await svc.update(short_code, data, owner=current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    return _link_to_out(link)




@router.delete("/{short_code}", response_model=MessageOut)
async def delete_link(
    short_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """(Auth required) Delete a short link."""
    svc = LinkService(db)
    try:
        deleted = await svc.delete(short_code, owner=current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")
    return MessageOut(message=f"Link '{short_code}' deleted successfully")




@router.post("/cleanup", response_model=MessageOut)
async def trigger_cleanup(
    body: UnusedTTLUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user_required),
):
    """(Auth required) Manually trigger deletion of unused links older than N days."""
    svc = LinkService(db)
    count = await svc.cleanup_unused(body.days)
    return MessageOut(message=f"Cleaned up {count} unused link(s) (TTL={body.days} days)")
