from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1 import api_router
from app.core.cache import close_redis
from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal
from app.utils.scheduler import start_scheduler, stop_scheduler
from app.services.link_service import LinkService


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    start_scheduler()
    yield
    stop_scheduler()
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description="""
## URL Shortener API

Most read endpoints are **public**. Mutations (update/delete) require a Bearer token.

### How to authenticate:
1. `POST /api/v1/auth/register` — create account
2. `POST /api/v1/auth/login` — get token from response
3. Click **Authorize** above → paste token into **HTTPBearer** field → Authorize
""",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/{short_code}", include_in_schema=False)
async def redirect(short_code: str):
    async with AsyncSessionLocal() as db:
        svc = LinkService(db)
        original_url = await svc.get_redirect(short_code)
        await db.commit()
    if not original_url:
        raise HTTPException(status_code=404, detail="Link not found or expired")
    return RedirectResponse(url=original_url, status_code=302)


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "URL Shortener API", "docs": "/docs"}
