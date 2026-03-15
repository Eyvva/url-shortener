"""Background scheduler for periodic link cleanup tasks."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.link_service import LinkService

scheduler = AsyncIOScheduler()


async def _run_expire():
    """Soft-delete links whose expires_at has passed."""
    async with AsyncSessionLocal() as db:
        svc = LinkService(db)
        count = await svc.expire_old_links()
        await db.commit()
        if count:
            print(f"[scheduler] Expired {count} link(s)")


async def _run_cleanup_unused():
    """Remove links unused for UNUSED_LINK_TTL_DAYS days."""
    async with AsyncSessionLocal() as db:
        svc = LinkService(db)
        count = await svc.cleanup_unused(settings.UNUSED_LINK_TTL_DAYS)
        await db.commit()
        if count:
            print(f"[scheduler] Cleaned {count} unused link(s)")


def start_scheduler():
    scheduler.add_job(_run_expire, IntervalTrigger(minutes=1), id="expire_links", replace_existing=True)
    scheduler.add_job(_run_cleanup_unused, IntervalTrigger(hours=1), id="cleanup_unused", replace_existing=True)
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown(wait=False)
