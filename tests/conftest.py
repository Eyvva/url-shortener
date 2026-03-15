"""
Test configuration.

Uses SQLite (in-memory) instead of PostgreSQL.
BigInteger is replaced with Integer via SQLAlchemy type override for SQLite.
Redis is replaced by an in-memory fake.
"""
import asyncio
from typing import Any, AsyncGenerator, Optional
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool


from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
SQLiteTypeCompiler.visit_big_integer = lambda self, type_, **kw: "INTEGER"

from app.core.database import Base, get_db
import app.models.models  
from app.main import app


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)



class FakeRedis:
    def __init__(self):
        self._store: dict = {}

    async def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    async def set(self, key: str, value: Any, ex: int = None) -> None:
        self._store[key] = value

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self._store.pop(k, None)

    async def incr(self, key: str) -> int:
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = str(val)
        return val

    async def aclose(self):
        pass


_fake_redis = FakeRedis()



@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def reset_redis():
    _fake_redis._store.clear()
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session
        await db_session.flush()

    app.dependency_overrides[get_db] = override_get_db

    with patch("app.core.cache._redis_client", _fake_redis), \
         patch("app.core.cache.get_redis", return_value=_fake_redis), \
         patch("app.utils.scheduler.start_scheduler"), \
         patch("app.utils.scheduler.stop_scheduler"), \
         patch("app.main.AsyncSessionLocal", TestSessionLocal):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()



async def register_and_login(client: AsyncClient, username: str = "testuser") -> dict:
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@test.com", "password": "secret123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123"},
    )
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}
