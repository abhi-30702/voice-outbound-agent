from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import Base
from app.db.session import get_engine


async def create_tables() -> None:
    """
    Create all tables defined in models.
    Run this on first app startup or in tests.
    """
    engine = await get_engine()
    async with engine.begin() as conn:
        # Create agent_operations schema if not exists
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS agent_operations"))
        # Create tables
        await conn.run_sync(Base.metadata.create_all)


async def check_db_connectivity() -> bool:
    """
    Check if database is reachable.
    Returns True if connected, False otherwise.
    """
    try:
        engine = await get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connectivity check failed: {e}")
        return False


async def check_migration_status() -> str | None:
    """
    Check current Alembic migration version.
    Returns version string or None if alembic_version table doesn't exist.
    """
    try:
        engine = await get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT version_num FROM alembic_version ORDER BY installed_on DESC LIMIT 1")
            )
            row = result.fetchone()
            return row[0] if row else None
    except Exception as e:
        print(f"Migration status check failed: {e}")
        return None


async def get_db_readiness_probe() -> dict:
    """
    Return readiness probe status for Kubernetes/Docker.
    Useful for health endpoints: /health/db
    """
    connectivity = await check_db_connectivity()
    migration_version = await check_migration_status()

    return {
        "status": "ready" if connectivity else "not_ready",
        "connectivity": connectivity,
        "migration_version": migration_version,
    }
