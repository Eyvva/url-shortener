from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_TITLE: str = "URL Shortener API"
    APP_VERSION: str = "1.0.0"
    BASE_URL: str = "http://localhost:8000"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/url_shortener"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 3600          # 1 hour default cache TTL
    POPULAR_LINK_TTL: int = 86400  # 24h for popular links cache
    REDIRECT_CACHE_TTL: int = 300  # 5 min for redirect cache

    # Auth / JWT
    SECRET_KEY: str = "supersecretkey-change-in-production-please"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Business logic
    SHORT_CODE_LENGTH: int = 7
    MAX_CUSTOM_ALIAS_LENGTH: int = 50
    UNUSED_LINK_TTL_DAYS: int = 30   # auto-delete after N days without usage
    POPULAR_THRESHOLD: int = 100     # clicks needed to be "popular"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
