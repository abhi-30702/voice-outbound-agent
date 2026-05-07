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


async def init_db_engine() -> AsyncEngine:
    """Initialize and return the async database engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.SQLALCHEMY_ECHO,
            pool_size=settings.POOL_SIZE,
            max_overflow=settings.MAX_OVERFLOW,
            future=True,
        )
    return _engine


def init_session_factory() -> async_sessionmaker:
    """Initialize and return the async session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        if _engine is None:
            raise RuntimeError("Engine not initialized. Call init_db_engine() first.")
        _SessionLocal = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _SessionLocal


async def get_engine() -> AsyncEngine:
    """Get or initialize the database engine."""
    global _engine
    if _engine is None:
        await init_db_engine()
    return _engine


async def get_session_factory() -> async_sessionmaker:
    """Get or initialize the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        init_session_factory()
    return _SessionLocal


async def close_db() -> None:
    """Close the database engine on app shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
