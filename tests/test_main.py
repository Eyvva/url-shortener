"""Tests for app/main.py — root endpoint and lifespan."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """GET / should return a welcome JSON payload."""
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "URL Shortener API"
    assert "docs" in body


@pytest.mark.asyncio
async def test_lifespan_startup_and_shutdown():
    """Lifespan runs create_all, starts/stops scheduler, closes redis and disposes engine."""
    from app.main import lifespan, app as fastapi_app

    mock_conn = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.begin.return_value = mock_cm
    mock_engine.dispose = AsyncMock()

    with patch("app.main.engine", mock_engine), \
         patch("app.main.start_scheduler") as mock_start, \
         patch("app.main.stop_scheduler") as mock_stop, \
         patch("app.main.close_redis", new_callable=AsyncMock) as mock_close:

        async with lifespan(fastapi_app):
            mock_start.assert_called_once()
            mock_conn.run_sync.assert_called_once()

        mock_stop.assert_called_once()
        mock_close.assert_called_once()
        mock_engine.dispose.assert_called_once()
