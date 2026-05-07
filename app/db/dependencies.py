from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.db.session import get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI routes to get a database session.

    Usage:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    factory = await get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()
