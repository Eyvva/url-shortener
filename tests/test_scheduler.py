"""Тесты фонового планировщика."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

from app.utils.scheduler import start_scheduler, stop_scheduler


def test_start_scheduler_adds_jobs():
    mock_scheduler = MagicMock()
    with patch("app.utils.scheduler.scheduler", mock_scheduler):
        start_scheduler()
        assert mock_scheduler.add_job.call_count == 2
        mock_scheduler.start.assert_called_once()


def test_stop_scheduler():
    mock_scheduler = MagicMock()
    with patch("app.utils.scheduler.scheduler", mock_scheduler):
        stop_scheduler()
        mock_scheduler.shutdown.assert_called_once_with(wait=False)


@pytest.mark.asyncio
async def test_expire_links_task():
    mock_svc = AsyncMock()
    mock_svc.expire_old_links = AsyncMock(return_value=2)

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=None)
    mock_db.commit = AsyncMock()

    with patch("app.utils.scheduler.AsyncSessionLocal", return_value=mock_db), \
         patch("app.utils.scheduler.LinkService", return_value=mock_svc):
        from app.utils.scheduler import _run_expire
        await _run_expire()
        mock_svc.expire_old_links.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_unused_task():
    mock_svc = AsyncMock()
    mock_svc.cleanup_unused = AsyncMock(return_value=3)

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=None)
    mock_db.commit = AsyncMock()

    with patch("app.utils.scheduler.AsyncSessionLocal", return_value=mock_db), \
         patch("app.utils.scheduler.LinkService", return_value=mock_svc):
        from app.utils.scheduler import _run_cleanup_unused
        await _run_cleanup_unused()
        mock_svc.cleanup_unused.assert_called_once()
