import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from app.core.settings import settings


# Global engine and session factory (initialized on app startup)
_engine: AsyncEngine | None = None
_SessionLocal: async_sessionmaker | None = None
_engine_lock: asyncio.Lock = asyncio.Lock()


async def init_db_engine() -> AsyncEngine:
    """Initialize and return the async database engine."""
    global _engine
    if _engine is None:
        async with _engine_lock:
            # Double-check pattern to avoid duplicate engines
            if _engine is None:
                _engine = create_async_engine(
                    settings.DATABASE_URL,
                    echo=settings.SQLALCHEMY_ECHO,
                    pool_size=settings.POOL_SIZE,
                    max_overflow=settings.MAX_OVERFLOW,
                )
    return _engine


async def init_session_factory() -> async_sessionmaker:
    """Initialize and return the async session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = await init_db_engine()
        _SessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _SessionLocal


async def get_engine() -> AsyncEngine:
    """Get or initialize the database engine."""
    return await init_db_engine()


async def get_session_factory() -> async_sessionmaker:
    """Get or initialize the session factory."""
    return await init_session_factory()


async def close_db() -> None:
    """Close the database engine on app shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
