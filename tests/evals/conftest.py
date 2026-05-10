"""Real-DB fixtures for tests/evals/.

db_engine  — session-scoped; runs `alembic upgrade head` once, disposes on teardown.
db_session — function-scoped; wraps each test in a SAVEPOINT that rolls back after
             the test, so inserts are never committed to the real database.

WARNING: Do NOT run with pytest-xdist (-n flag). SAVEPOINT patterns over shared
async connections are unstable under parallel workers. Always run sequentially:
  pytest tests/evals/ -v
"""
import subprocess
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.settings import settings

PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def db_engine():
    """Run Alembic migrations once; yield engine; downgrade on teardown."""
    subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True,
        cwd=str(PROJECT_ROOT),
    )
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    yield engine
    engine.sync_engine.dispose()
    subprocess.run(
        ["alembic", "downgrade", "base"],
        check=True,
        cwd=str(PROJECT_ROOT),
    )


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Per-test AsyncSession inside a SAVEPOINT — always rolls back."""
    async with db_engine.connect() as conn:
        trans = await conn.begin()
        nested = await conn.begin_nested()   # SAVEPOINT
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        if nested.is_active:
            await nested.rollback()
        await trans.rollback()
