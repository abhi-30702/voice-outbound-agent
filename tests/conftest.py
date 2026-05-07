"""Pytest fixtures for database tests."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.db.base import Base
from app.core.settings import settings


@pytest_asyncio.fixture
async def test_engine():
    """Create a test database engine."""
    # Use the configured DATABASE_URL for tests
    # In CI, this should point to a test database
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # Set to True for SQL debugging
    )

    yield engine

    # Cleanup: dispose of the engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Create a test database session with automatic rollback."""
    # Create a connection and begin a transaction
    async with test_engine.begin() as connection:
        # Start a transaction for this test
        transaction = await connection.begin()

        # Create a session factory for this transaction
        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        async with session_factory() as session:
            yield session

        # Rollback the transaction after the test
        await transaction.rollback()


@pytest_asyncio.fixture
async def db_with_tables(test_engine):
    """Create all tables in test database."""
    async with test_engine.begin() as conn:
        # Create schema
        await conn.execute("CREATE SCHEMA IF NOT EXISTS agent_operations")
        # Create tables from model metadata
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    # Cleanup: drop all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute("DROP SCHEMA IF EXISTS agent_operations")


@pytest.fixture
def anyio_backend():
    """Specify anyio backend for async fixtures."""
    return "asyncio"
