# tests/integration/test_db_connection.py
"""Integration tests for database connectivity and schema."""

import pytest
import pytest_asyncio
from sqlalchemy import text
from app.db.init_db import (
    check_db_connectivity,
    check_migration_status,
    create_tables,
    get_db_readiness_probe,
)
from app.db.session import init_db_engine, init_session_factory


@pytest_asyncio.fixture
async def db_engine():
    """Fixture to provide database engine for tests."""
    engine = await init_db_engine()
    yield engine


@pytest.mark.asyncio
class TestDatabaseConnectivity:
    """Test database connection and schema."""

    async def test_check_connectivity_succeeds(self):
        """Connectivity check should succeed if DB is reachable."""
        result = await check_db_connectivity()
        assert result is True

    async def test_check_migration_status_returns_version(self):
        """Migration status check should return version or None."""
        version = await check_migration_status()
        assert version is None or isinstance(version, str)

    async def test_readiness_probe_returns_dict(self):
        """Readiness probe should return dict with status."""
        probe = await get_db_readiness_probe()
        assert isinstance(probe, dict)
        assert "status" in probe
        assert "connectivity" in probe
        assert probe["status"] in ["ready", "not_ready"]
        assert isinstance(probe["connectivity"], bool)

    async def test_schema_agent_operations_exists(self, db_engine):
        """Schema agent_operations should exist after create_tables."""
        await create_tables()

        async with db_engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = 'agent_operations'
                """)
            )
            row = result.fetchone()
            assert row is not None, "Schema agent_operations should exist"

    async def test_all_tables_created(self, db_engine):
        """All required tables should be created."""
        await create_tables()

        expected_tables = [
            "campaigns",
            "leads",
            "call_logs",
            "call_transcripts",
            "dnc_registry",
        ]

        async with db_engine.connect() as conn:
            for table_name in expected_tables:
                result = await conn.execute(
                    text("""
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'agent_operations'
                        AND table_name = :table_name
                    """).bindparams(table_name=table_name)
                )
                row = result.fetchone()
                assert row is not None, f"Table {table_name} should exist"
