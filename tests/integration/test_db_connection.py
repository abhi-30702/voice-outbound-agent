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

    async def test_memories_role_has_correct_grants(self, db_engine):
        """Verify memories_role has SELECT/INSERT/UPDATE (no DELETE)."""
        # Create role if doesn't exist (safe for test)
        async with db_engine.connect() as conn:
            await conn.execute(text("CREATE ROLE IF NOT EXISTS memories_role"))
            await conn.commit()

        # Query information_schema for role grants
        async with db_engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT privilege_type, table_name
                    FROM information_schema.role_table_grants
                    WHERE grantee = 'memories_role'
                      AND table_schema = 'agent_operations'
                    ORDER BY table_name, privilege_type
                """)
            )
            grants = result.fetchall()

        # Build a set of (table, privilege) tuples
        grant_set = {(row[1], row[0]) for row in grants}

        # Verify expected grants exist
        expected_grants = {
            ("campaigns", "SELECT"),
            ("campaigns", "INSERT"),
            ("campaigns", "UPDATE"),
            ("leads", "SELECT"),
            ("leads", "INSERT"),
            ("leads", "UPDATE"),
            ("call_logs", "SELECT"),
            ("call_logs", "INSERT"),
            ("call_logs", "UPDATE"),
            ("call_transcripts", "SELECT"),
            ("call_transcripts", "INSERT"),
            ("dnc_registry", "SELECT"),
        }

        for expected in expected_grants:
            assert expected in grant_set, f"Missing grant: {expected[1]} on {expected[0]}"

        # Verify DELETE is NOT granted (security)
        delete_grants = {(row[1], row[0]) for row in grants if row[0] == "DELETE"}
        assert len(delete_grants) == 0, f"memories_role should NOT have DELETE privilege, found: {delete_grants}"

    async def test_dnc_check_query_with_parameterized_sql(self, db_engine):
        """Verify DNC check query works with parameterized SQL (NOT EXISTS pattern)."""
        # Ensure schema and tables exist
        await create_tables()

        # Insert test data
        async with db_engine.begin() as conn:
            # Insert a DNC phone
            await conn.execute(
                text("""
                    INSERT INTO agent_operations.dnc_registry
                    (id, phone_number, source, added_at)
                    VALUES (:id, :phone, :source, NOW())
                """),
                {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "phone": "+919876543210",
                    "source": "manual",
                }
            )

        # Test the parameterized DNC check query
        async with db_engine.connect() as conn:
            # Query: check if phone exists in DNC registry
            dnc_check = text("""
                SELECT EXISTS (
                    SELECT 1 FROM agent_operations.dnc_registry
                    WHERE phone_number = :phone_number
                )
            """)

            # Test: phone in DNC should return True
            result = await conn.execute(
                dnc_check,
                {"phone_number": "+919876543210"}
            )
            is_dnc = result.scalar()
            assert is_dnc is True, "Phone should be found in DNC registry"

            # Test: phone not in DNC should return False
            result = await conn.execute(
                dnc_check,
                {"phone_number": "+919999999999"}
            )
            is_dnc = result.scalar()
            assert is_dnc is False, "Phone should NOT be found in DNC registry"

    async def test_seed_script_idempotency(self, db_engine):
        """Verify seed script creates data once and is safe to rerun."""
        from app.db.session import init_session_factory
        from app.models import Campaign, Contact
        from sqlalchemy import select, func

        # Initialize for seeding
        await init_session_factory()

        # Run seed once
        from scripts.seed_db import seed_db
        await seed_db()

        # Count initial records
        async with db_engine.connect() as conn:
            campaign_count = await conn.execute(
                select(func.count()).select_from(Campaign)
            )
            campaign_count_1 = campaign_count.scalar()

            contact_count = await conn.execute(
                select(func.count()).select_from(Contact)
            )
            contact_count_1 = contact_count.scalar()

        # Run seed again (should not create duplicates)
        await seed_db()

        # Count records again
        async with db_engine.connect() as conn:
            campaign_count = await conn.execute(
                select(func.count()).select_from(Campaign)
            )
            campaign_count_2 = campaign_count.scalar()

            contact_count = await conn.execute(
                select(func.count()).select_from(Contact)
            )
            contact_count_2 = contact_count.scalar()

        # Verify counts unchanged (idempotent)
        assert campaign_count_1 == campaign_count_2, \
            f"Campaign count changed after rerun: {campaign_count_1} -> {campaign_count_2}"
        assert contact_count_1 == contact_count_2, \
            f"Contact count changed after rerun: {contact_count_1} -> {contact_count_2}"
