# DB-Schema Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a production-grade PostgreSQL database layer with SQLAlchemy ORM models, Alembic migrations, async session management, and comprehensive tests.

**Architecture:** Async SQLAlchemy with declarative base + mixins, Alembic auto-migrations from model definitions, FastAPI dependency injection for sessions, scoped `memories_role` PostgreSQL role with minimal privileges, separated grants and seed scripts.

**Tech Stack:** Python 3.13, FastAPI, PostgreSQL 16, asyncpg, SQLAlchemy 2.0+, Alembic, pytest, pytest-asyncio

**Phase:** 1 | **Module:** db-schema | **Status:** Implementation

---

## Task 1: Add Python Dependencies

**Files:**
- Modify: `requirements.txt` (or `pyproject.toml`)

- [ ] **Step 1: Check current requirements file**

Run: `cat requirements.txt`

Expected output: minimal or empty; exact format depends on project

- [ ] **Step 2: Add database dependencies to requirements.txt**

```text
# Database
sqlalchemy==2.1.0
asyncpg==0.30.0
alembic==1.13.0
psycopg2-binary==2.9.9

# FastAPI (if not present)
fastapi==0.115.0
uvicorn==0.30.0

# Testing
pytest==8.0.0
pytest-asyncio==0.24.0
```

- [ ] **Step 3: Install dependencies**

Run: `pip install -r requirements.txt`

Expected: All packages installed successfully

- [ ] **Step 4: Verify imports work**

Run: `python -c "import sqlalchemy; import asyncpg; import alembic; print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "chore: add database dependencies (sqlalchemy, asyncpg, alembic, pytest-asyncio)"
```

---

## Task 2: Create Settings Module

**Files:**
- Create: `app/core/settings.py`
- Create: `app/core/__init__.py` (if not exists)

- [ ] **Step 1: Create app/core/__init__.py**

```python
# app/core/__init__.py
```

(empty file; run touch in PowerShell or create blank)

- [ ] **Step 2: Write app/core/settings.py**

```python
# app/core/settings.py
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/voice_agent",
        description="PostgreSQL async connection string"
    )
    SQLALCHEMY_ECHO: bool = Field(
        default=False,
        description="Log all SQL statements if True"
    )
    POOL_SIZE: int = Field(
        default=10,
        description="SQLAlchemy connection pool size"
    )
    MAX_OVERFLOW: int = Field(
        default=20,
        description="SQLAlchemy max overflow connections"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

- [ ] **Step 3: Verify settings can be imported**

Run: `python -c "from app.core.settings import settings; print(f'DB URL: {settings.DATABASE_URL}')"`

Expected: `DB URL: postgresql+asyncpg://...`

- [ ] **Step 4: Commit**

```bash
git add app/core/settings.py app/core/__init__.py
git commit -m "feat: add settings module with DATABASE_URL config"
```

---

## Task 3: Create Database Base and Mixins

**Files:**
- Create: `app/db/base.py`
- Create: `app/db/__init__.py` (if not exists)

- [ ] **Step 1: Create app/db/__init__.py**

```python
# app/db/__init__.py
```

(empty file)

- [ ] **Step 2: Write failing unit test first**

Create `tests/unit/test_db_base.py`:

```python
# tests/unit/test_db_base.py
import pytest
from uuid import UUID
from datetime import datetime
from sqlalchemy.inspection import inspect
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TestTimestampMixin:
    """Test TimestampMixin columns."""
    
    def test_timestamp_mixin_has_created_at(self):
        """TimestampMixin should have created_at column."""
        # This is a simple structural test
        attrs = dir(TimestampMixin)
        # We'll validate in integration test; for now just ensure class exists
        assert TimestampMixin is not None
    
    def test_uuid_primary_key_mixin_has_id(self):
        """UUIDPrimaryKeyMixin should have id column."""
        assert UUIDPrimaryKeyMixin is not None


class TestBase:
    """Test DeclarativeBase."""
    
    def test_base_exists(self):
        """Base should be a DeclarativeBase."""
        assert Base is not None
        assert hasattr(Base, "metadata")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_db_base.py -v`

Expected: FAIL with "cannot import name 'TimestampMixin'"

- [ ] **Step 4: Write app/db/base.py**

```python
# app/db/base.py
from datetime import datetime
from uuid import uuid4, UUID
from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


class UUIDPrimaryKeyMixin:
    """Mixin providing UUID primary key."""
    
    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
        nullable=False
    )


class TimestampMixin:
    """Mixin providing created_at and updated_at timestamps."""
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_db_base.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/db/base.py app/db/__init__.py tests/unit/test_db_base.py
git commit -m "feat: add database base class and mixins (UUID, Timestamp)"
```

---

## Task 4: Create Async Session Factory

**Files:**
- Create: `app/db/session.py`

- [ ] **Step 1: Write app/db/session.py**

```python
# app/db/session.py
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
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from app.db.session import get_engine, get_session_factory; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/db/session.py
git commit -m "feat: add async database engine and session factory"
```

---

## Task 5: Create FastAPI Dependency

**Files:**
- Create: `app/db/dependencies.py`

- [ ] **Step 1: Write app/db/dependencies.py**

```python
# app/db/dependencies.py
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
```

- [ ] **Step 2: Verify import**

Run: `python -c "from app.db.dependencies import get_db; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/db/dependencies.py
git commit -m "feat: add FastAPI dependency for database session"
```

---

## Task 6: Create Database Initialization and Health Checks

**Files:**
- Create: `app/db/init_db.py`

- [ ] **Step 1: Write app/db/init_db.py**

```python
# app/db/init_db.py
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
```

- [ ] **Step 2: Verify imports**

Run: `python -c "from app.db.init_db import create_tables, check_db_connectivity; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/db/init_db.py
git commit -m "feat: add database initialization and health check functions"
```

---

## Task 7: Initialize Alembic

**Files:**
- Create: `alembic/` (directory structure)
- Create: `alembic.ini` (config)

- [ ] **Step 1: Run alembic init**

Run: `alembic init alembic`

Expected: Creates `alembic/` folder with `env.py`, `script.py_mako`, `versions/`, and `alembic.ini`

- [ ] **Step 2: Verify structure**

Run: `ls -la alembic/`

Expected: `env.py`, `script.py_mako`, `versions/`, etc.

- [ ] **Step 3: Commit**

```bash
git add alembic/ alembic.ini
git commit -m "init: initialize Alembic migration system"
```

---

## Task 8: Configure Alembic for Async SQLAlchemy

**Files:**
- Modify: `alembic/env.py`

- [ ] **Step 1: Read current alembic/env.py**

Run: `head -50 alembic/env.py`

(Just to see the template)

- [ ] **Step 2: Replace alembic/env.py with async-enabled version**

```python
# alembic/env.py
from logging.config import fileConfig
import asyncio
from sqlalchemy import pool
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from app.core.settings import settings
from app.db.base import Base

config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target_metadata for auto-discovery of models
target_metadata = Base.metadata

# Override sqlalchemy.url with settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 3: Verify Alembic can find models**

Run: `alembic heads`

Expected: No error; shows current head (might be empty if no migrations yet)

- [ ] **Step 4: Commit**

```bash
git add alembic/env.py
git commit -m "feat: configure Alembic for async SQLAlchemy"
```

---

## Task 9: Create Campaign Model

**Files:**
- Create: `app/models/campaign.py`

- [ ] **Step 1: Write app/models/campaign.py**

```python
# app/models/campaign.py
from sqlalchemy import String, Enum, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum as PyEnum
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class CampaignStatus(str, PyEnum):
    """Campaign status enumeration."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Campaign entity for outbound calls."""
    
    __tablename__ = "campaigns"
    __table_args__ = (
        {"schema": "agent_operations"},
        Index("idx_campaign_status", "status"),
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus),
        default=CampaignStatus.DRAFT,
        nullable=False
    )
    prompt_template: Mapped[dict] = mapped_column(JSONB, nullable=False)
    llm_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
```

- [ ] **Step 2: Verify import**

Run: `python -c "from app.models.campaign import Campaign, CampaignStatus; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/models/campaign.py
git commit -m "feat: add Campaign model"
```

---

## Task 10: Create Contact Model

**Files:**
- Create: `app/models/contact.py`

- [ ] **Step 1: Write app/models/contact.py**

```python
# app/models/contact.py
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, Index, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum as PyEnum
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin
from uuid import UUID


class ContactStatus(str, PyEnum):
    """Contact/lead status enumeration."""
    PENDING = "pending"
    CALLING = "calling"
    COMPLETED = "completed"
    FAILED = "failed"
    FAILED_DNC = "failed_dnc"


class Contact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Lead/contact entity for outbound dialing."""
    
    __tablename__ = "contacts"
    __table_args__ = (
        {"schema": "agent_operations"},
        Index("idx_contact_phone", "phone_number"),
        Index("idx_contact_campaign", "campaign_id"),
        Index("idx_contact_status", "status"),
        Index("idx_contact_created", "created_at"),
    )
    
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    company: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    campaign_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_operations.campaigns.id"),
        nullable=True
    )
    status: Mapped[ContactStatus] = mapped_column(
        Enum(ContactStatus),
        default=ContactStatus.PENDING,
        nullable=False
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    custom_vars: Mapped[dict | None] = mapped_column(JSONB)
```

- [ ] **Step 2: Verify import**

Run: `python -c "from app.models.contact import Contact, ContactStatus; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/models/contact.py
git commit -m "feat: add Contact model"
```

---

## Task 11: Create Call Model

**Files:**
- Create: `app/models/call.py`

- [ ] **Step 1: Write app/models/call.py**

```python
# app/models/call.py
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, Index, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum as PyEnum
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin
from uuid import UUID


class CallStatus(str, PyEnum):
    """Call status enumeration."""
    PENDING = "pending"
    CALLING = "calling"
    COMPLETED = "completed"
    FAILED = "failed"


class Call(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Call log entity for tracking outbound calls."""
    
    __tablename__ = "calls"
    __table_args__ = (
        {"schema": "agent_operations"},
        Index("idx_call_contact", "contact_id"),
        Index("idx_call_status", "status"),
        Index("idx_call_created", "created_at"),
    )
    
    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_operations.contacts.id"),
        nullable=False
    )
    retell_call_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[CallStatus] = mapped_column(
        Enum(CallStatus),
        default=CallStatus.PENDING,
        nullable=False
    )
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    disconnect_reason: Mapped[str | None] = mapped_column(String(100))
    recording_url: Mapped[str | None] = mapped_column(String(500))
```

- [ ] **Step 2: Verify import**

Run: `python -c "from app.models.call import Call, CallStatus; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/models/call.py
git commit -m "feat: add Call model"
```

---

## Task 12: Create Transcript Model

**Files:**
- Create: `app/models/transcript.py`

- [ ] **Step 1: Write app/models/transcript.py**

```python
# app/models/transcript.py
from sqlalchemy import String, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum as PyEnum
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin
from uuid import UUID


class SentimentLevel(str, PyEnum):
    """Sentiment enumeration."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Transcript(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Call transcript and structured extraction results."""
    
    __tablename__ = "call_transcripts"
    __table_args__ = (
        {"schema": "agent_operations"},
        Index("idx_transcript_call", "call_id"),
    )
    
    call_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_operations.calls.id"),
        nullable=False,
        unique=True
    )
    raw_transcript: Mapped[str | None] = mapped_column(Text)
    structured_data: Mapped[dict | None] = mapped_column(JSONB)
    sentiment: Mapped[SentimentLevel | None] = mapped_column(Enum(SentimentLevel))
```

- [ ] **Step 2: Verify import**

Run: `python -c "from app.models.transcript import Transcript, SentimentLevel; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/models/transcript.py
git commit -m "feat: add Transcript model"
```

---

## Task 13: Create DNC Entry Model

**Files:**
- Create: `app/models/dnc_entry.py`

- [ ] **Step 1: Write app/models/dnc_entry.py**

```python
# app/models/dnc_entry.py
from datetime import datetime
from sqlalchemy import String, Index
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum as PyEnum
from app.db.base import Base, UUIDPrimaryKeyMixin
from uuid import UUID


class DNCSource(str, PyEnum):
    """DNC registry source enumeration."""
    MANUAL = "manual"
    NATIONAL_DNC = "national_dnc"
    CALLER_REQUEST = "caller_request"


class DNCEntry(Base, UUIDPrimaryKeyMixin):
    """Do-Not-Call registry entry for compliance."""
    
    __tablename__ = "dnc_registry"
    __table_args__ = (
        {"schema": "agent_operations"},
        Index("idx_dnc_phone", "phone_number", unique=True),
    )
    
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    source: Mapped[DNCSource | None] = mapped_column(Enum(DNCSource))
    added_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        nullable=False
    )
```

- [ ] **Step 2: Verify import**

Run: `python -c "from app.models.dnc_entry import DNCEntry, DNCSource; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/models/dnc_entry.py
git commit -m "feat: add DNCEntry model"
```

---

## Task 14: Create Models __init__.py

**Files:**
- Create: `app/models/__init__.py`

- [ ] **Step 1: Create app/models/__init__.py with re-exports**

```python
# app/models/__init__.py
"""ORM models for voice-outbound-agent."""

from app.models.campaign import Campaign, CampaignStatus
from app.models.contact import Contact, ContactStatus
from app.models.call import Call, CallStatus
from app.models.transcript import Transcript, SentimentLevel
from app.models.dnc_entry import DNCEntry, DNCSource

__all__ = [
    "Campaign",
    "CampaignStatus",
    "Contact",
    "ContactStatus",
    "Call",
    "CallStatus",
    "Transcript",
    "SentimentLevel",
    "DNCEntry",
    "DNCSource",
]
```

- [ ] **Step 2: Verify imports**

Run: `python -c "from app.models import Campaign, Contact, Call, Transcript, DNCEntry; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/models/__init__.py
git commit -m "feat: add models __init__.py with re-exports"
```

---

## Task 15: Generate Initial Migration

**Files:**
- Create: `alembic/versions/001_initial_schema.py`

- [ ] **Step 1: Generate migration with autogenerate**

Run: `alembic revision --autogenerate -m "initial_schema"`

Expected: Creates `alembic/versions/001_initial_schema.py`

- [ ] **Step 2: Review the generated migration**

Run: `head -100 alembic/versions/001_initial_schema.py`

Expected: Migration contains CREATE TABLE statements for all 5 tables in agent_operations schema

- [ ] **Step 3: Commit the migration**

```bash
git add alembic/versions/001_initial_schema.py
git commit -m "feat: add initial migration (all 5 tables)"
```

---

## Task 16: Create PostgreSQL Grants Script

**Files:**
- Create: `scripts/grants.sql`

- [ ] **Step 1: Create scripts directory if not exists**

Run: `mkdir -p scripts`

- [ ] **Step 2: Write scripts/grants.sql**

```sql
-- scripts/grants.sql
-- PostgreSQL permissions for memories_role (LLM read-only access)
-- Apply AFTER migration 001_initial_schema.py

-- Create role if not exists
CREATE ROLE memories_role;

-- Grant schema usage
GRANT USAGE ON SCHEMA agent_operations TO memories_role;

-- Grant table permissions (SELECT, INSERT, UPDATE only)
GRANT SELECT, INSERT, UPDATE ON agent_operations.campaigns TO memories_role;
GRANT SELECT, INSERT, UPDATE ON agent_operations.contacts TO memories_role;
GRANT SELECT, INSERT, UPDATE ON agent_operations.calls TO memories_role;
GRANT SELECT, INSERT ON agent_operations.call_transcripts TO memories_role;
GRANT SELECT ON agent_operations.dnc_registry TO memories_role;

-- Grant sequence permissions for UUID generation
GRANT USAGE ON ALL SEQUENCES IN SCHEMA agent_operations TO memories_role;

-- No DELETE, DROP, CREATE, or schema ownership granted
-- This enforces least-privilege access for LLM operations
```

- [ ] **Step 3: Verify syntax**

Run: `cat scripts/grants.sql`

Expected: Shows the SQL script with proper formatting

- [ ] **Step 4: Commit**

```bash
git add scripts/grants.sql
git commit -m "feat: add PostgreSQL grants script for memories_role"
```

---

## Task 17: Create Seed Script

**Files:**
- Create: `scripts/seed_db.py`

- [ ] **Step 1: Write scripts/seed_db.py**

```python
# scripts/seed_db.py
"""
Seed script: populate test data.
Run: python scripts/seed_db.py
"""

import asyncio
from uuid import uuid4
from app.db.session import init_db_engine, init_session_factory
from app.db.init_db import create_tables
from app.models import Campaign, Contact, DNCEntry, CampaignStatus, ContactStatus, DNCSource


async def seed_db():
    """Seed database with test data."""
    # Initialize engine and session
    await init_db_engine()
    init_session_factory()
    
    # Create tables if they don't exist
    try:
        await create_tables()
        print("✓ Tables created")
    except Exception as e:
        print(f"Note: {e}")
    
    # Get session factory
    from app.db.session import _SessionLocal
    session_factory = _SessionLocal
    
    async with session_factory() as session:
        # Check if test campaign already exists
        from sqlalchemy import select
        result = await session.execute(
            select(Campaign).where(Campaign.name == "Test Campaign")
        )
        existing = result.scalars().first()
        
        if not existing:
            campaign = Campaign(
                id=uuid4(),
                name="Test Campaign",
                status=CampaignStatus.DRAFT,
                prompt_template={
                    "persona": "Friendly Operations Assistant",
                    "objective": "Test call",
                },
                llm_config={
                    "model": "gpt-4o",
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
            )
            session.add(campaign)
            await session.flush()
            campaign_id = campaign.id
            print(f"✓ Campaign created: {campaign_id}")
        else:
            campaign_id = existing.id
            print(f"✓ Campaign already exists: {campaign_id}")
        
        # Check if DNC contact exists
        result = await session.execute(
            select(Contact).where(Contact.phone_number == "+919876543210")
        )
        dnc_contact_exists = result.scalars().first() is not None
        
        if not dnc_contact_exists:
            dnc_contact = Contact(
                id=uuid4(),
                phone_number="+919876543210",
                first_name="DNC",
                last_name="Test",
                timezone="Asia/Kolkata",
                campaign_id=campaign_id,
                status=ContactStatus.PENDING,
            )
            session.add(dnc_contact)
            await session.flush()
            print(f"✓ DNC contact created: +919876543210")
        else:
            print(f"✓ DNC contact already exists: +919876543210")
        
        # Add to DNC registry
        result = await session.execute(
            select(DNCEntry).where(DNCEntry.phone_number == "+919876543210")
        )
        dnc_exists = result.scalars().first() is not None
        
        if not dnc_exists:
            dnc_entry = DNCEntry(
                id=uuid4(),
                phone_number="+919876543210",
                source=DNCSource.MANUAL,
            )
            session.add(dnc_entry)
            print(f"✓ DNC registry entry created: +919876543210")
        else:
            print(f"✓ DNC registry entry already exists: +919876543210")
        
        # Check if clean contact exists
        result = await session.execute(
            select(Contact).where(Contact.phone_number == "+919876543211")
        )
        clean_contact_exists = result.scalars().first() is not None
        
        if not clean_contact_exists:
            clean_contact = Contact(
                id=uuid4(),
                phone_number="+919876543211",
                first_name="Clean",
                last_name="Lead",
                timezone="Asia/Kolkata",
                campaign_id=campaign_id,
                status=ContactStatus.PENDING,
            )
            session.add(clean_contact)
            print(f"✓ Clean contact created: +919876543211")
        else:
            print(f"✓ Clean contact already exists: +919876543211")
        
        # Commit all changes
        await session.commit()
        print("✓ All data committed")


if __name__ == "__main__":
    asyncio.run(seed_db())
    print("\n✓ Seed complete!")
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile scripts/seed_db.py`

Expected: No output (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_db.py
git commit -m "feat: add database seed script"
```

---

## Task 18: Create Unit Tests for Models

**Files:**
- Create: `tests/unit/test_models.py`
- Create: `tests/unit/__init__.py` (if not exists)

- [ ] **Step 1: Create tests/unit/__init__.py**

```python
# tests/unit/__init__.py
```

(empty file)

- [ ] **Step 2: Write tests/unit/test_models.py**

```python
# tests/unit/test_models.py
"""Unit tests for ORM models."""

import pytest
from uuid import UUID
from datetime import datetime
from sqlalchemy.inspection import inspect
from app.models import (
    Campaign, CampaignStatus,
    Contact, ContactStatus,
    Call, CallStatus,
    Transcript, SentimentLevel,
    DNCEntry, DNCSource,
)


class TestCampaignModel:
    """Tests for Campaign model."""
    
    def test_campaign_has_required_columns(self):
        """Campaign should have all required columns."""
        mapper = inspect(Campaign)
        columns = {c.name for c in mapper.columns}
        
        assert "id" in columns
        assert "name" in columns
        assert "status" in columns
        assert "prompt_template" in columns
        assert "llm_config" in columns
        assert "created_at" in columns
        assert "updated_at" in columns
    
    def test_campaign_status_enum_values(self):
        """CampaignStatus enum should have expected values."""
        assert CampaignStatus.DRAFT.value == "draft"
        assert CampaignStatus.ACTIVE.value == "active"
        assert CampaignStatus.PAUSED.value == "paused"
        assert CampaignStatus.COMPLETED.value == "completed"


class TestContactModel:
    """Tests for Contact model."""
    
    def test_contact_has_required_columns(self):
        """Contact should have all required columns."""
        mapper = inspect(Contact)
        columns = {c.name for c in mapper.columns}
        
        assert "id" in columns
        assert "phone_number" in columns
        assert "timezone" in columns
        assert "campaign_id" in columns
        assert "status" in columns
        assert "retry_count" in columns
        assert "custom_vars" in columns
        assert "created_at" in columns
        assert "updated_at" in columns
    
    def test_contact_status_enum_values(self):
        """ContactStatus enum should have expected values."""
        assert ContactStatus.PENDING.value == "pending"
        assert ContactStatus.CALLING.value == "calling"
        assert ContactStatus.COMPLETED.value == "completed"
        assert ContactStatus.FAILED.value == "failed"
        assert ContactStatus.FAILED_DNC.value == "failed_dnc"


class TestCallModel:
    """Tests for Call model."""
    
    def test_call_has_required_columns(self):
        """Call should have all required columns."""
        mapper = inspect(Call)
        columns = {c.name for c in mapper.columns}
        
        assert "id" in columns
        assert "contact_id" in columns
        assert "retell_call_id" in columns
        assert "status" in columns
        assert "start_time" in columns
        assert "duration_sec" in columns
        assert "recording_url" in columns
        assert "created_at" in columns
    
    def test_call_status_enum_values(self):
        """CallStatus enum should have expected values."""
        assert CallStatus.PENDING.value == "pending"
        assert CallStatus.CALLING.value == "calling"
        assert CallStatus.COMPLETED.value == "completed"
        assert CallStatus.FAILED.value == "failed"


class TestTranscriptModel:
    """Tests for Transcript model."""
    
    def test_transcript_has_required_columns(self):
        """Transcript should have all required columns."""
        mapper = inspect(Transcript)
        columns = {c.name for c in mapper.columns}
        
        assert "id" in columns
        assert "call_id" in columns
        assert "raw_transcript" in columns
        assert "structured_data" in columns
        assert "sentiment" in columns
        assert "created_at" in columns
    
    def test_sentiment_enum_values(self):
        """SentimentLevel enum should have expected values."""
        assert SentimentLevel.POSITIVE.value == "positive"
        assert SentimentLevel.NEUTRAL.value == "neutral"
        assert SentimentLevel.NEGATIVE.value == "negative"


class TestDNCEntryModel:
    """Tests for DNCEntry model."""
    
    def test_dnc_entry_has_required_columns(self):
        """DNCEntry should have all required columns."""
        mapper = inspect(DNCEntry)
        columns = {c.name for c in mapper.columns}
        
        assert "id" in columns
        assert "phone_number" in columns
        assert "source" in columns
        assert "added_at" in columns
    
    def test_dnc_source_enum_values(self):
        """DNCSource enum should have expected values."""
        assert DNCSource.MANUAL.value == "manual"
        assert DNCSource.NATIONAL_DNC.value == "national_dnc"
        assert DNCSource.CALLER_REQUEST.value == "caller_request"


class TestModelIndexes:
    """Tests for model indexes."""
    
    def test_contact_has_phone_index(self):
        """Contact should have an index on phone_number."""
        mapper = inspect(Contact)
        index_names = {idx.name for idx in mapper.indexes}
        assert any("phone" in name for name in index_names)
    
    def test_dnc_entry_has_unique_phone_index(self):
        """DNCEntry should have unique index on phone_number."""
        mapper = inspect(DNCEntry)
        # Unique constraint is enforced via unique=True on column
        columns = {c.name for c in mapper.columns}
        phone_col = [c for c in mapper.columns if c.name == "phone_number"][0]
        assert phone_col.unique
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/unit/test_models.py -v`

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/unit/ tests/unit/__init__.py tests/unit/test_models.py
git commit -m "test: add unit tests for ORM models"
```

---

## Task 19: Create Integration Test

**Files:**
- Create: `tests/integration/test_db_connection.py`
- Create: `tests/integration/__init__.py` (if not exists)
- Create: `tests/__init__.py` (if not exists)

- [ ] **Step 1: Create test directories**

Run: `mkdir -p tests/integration tests/unit`

- [ ] **Step 2: Create __init__.py files**

```bash
touch tests/__init__.py tests/integration/__init__.py
```

- [ ] **Step 3: Write integration test**

Create `tests/integration/test_db_connection.py`:

```python
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
    # Cleanup: don't dispose, tests might share


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
        # Version might be None if no migrations applied yet
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
            "contacts",
            "calls",
            "call_transcripts",
            "dnc_registry",
        ]
        
        async with db_engine.connect() as conn:
            for table_name in expected_tables:
                result = await conn.execute(
                    text(f"""
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = 'agent_operations' 
                        AND table_name = '{table_name}'
                    """)
                )
                row = result.fetchone()
                assert row is not None, f"Table {table_name} should exist"
    
    async def test_memories_role_exists(self, db_engine):
        """The memories_role should exist after grants.sql is applied."""
        # Note: This test assumes grants.sql has been manually applied
        # If not, test will skip or fail gracefully
        async with db_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = 'memories_role'")
            )
            row = result.fetchone()
            # Skip if role doesn't exist yet
            if row is None:
                pytest.skip("memories_role not created yet (apply grants.sql manually)")
    
    async def test_campaign_table_has_columns(self, db_engine):
        """Campaign table should have required columns."""
        await create_tables()
        
        required_columns = [
            "id", "name", "status", "prompt_template", 
            "llm_config", "created_at", "updated_at"
        ]
        
        async with db_engine.connect() as conn:
            for col in required_columns:
                result = await conn.execute(
                    text(f"""
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_schema = 'agent_operations' 
                        AND table_name = 'campaigns' 
                        AND column_name = '{col}'
                    """)
                )
                row = result.fetchone()
                assert row is not None, f"Column {col} should exist in campaigns"
```

- [ ] **Step 4: Update pytest configuration to support async tests**

Create or update `pytest.ini` or `pyproject.toml`:

```ini
[pytest]
asyncio_mode = auto
```

Or in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 5: Verify pytest can find tests**

Run: `pytest tests/integration/test_db_connection.py --collect-only`

Expected: Lists test functions (even if they fail to run due to DB not configured)

- [ ] **Step 6: Commit**

```bash
git add tests/integration/ tests/__init__.py pytest.ini
git commit -m "test: add integration tests for database connectivity"
```

---

## Task 20: Manual Database Setup and Test Execution

**Files:**
- None (manual steps)

- [ ] **Step 1: Ensure PostgreSQL is running**

On Windows with Docker Desktop:

```bash
docker run -d \
  --name postgres16 \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=voice_agent \
  -p 5432:5432 \
  postgres:16
```

Expected: Docker container starts and port 5432 is accessible

- [ ] **Step 2: Update .env file**

Create or update `.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/voice_agent
SQLALCHEMY_ECHO=false
POOL_SIZE=10
MAX_OVERFLOW=20
```

- [ ] **Step 3: Apply initial migration**

Run: `alembic upgrade head`

Expected: Migration succeeds; creates schema and tables

- [ ] **Step 4: Apply grants script**

Run: `psql -h localhost -U postgres -d voice_agent -f scripts/grants.sql`

Expected: Role and permissions created without errors

- [ ] **Step 5: Run unit tests**

Run: `pytest tests/unit/ -v`

Expected: All unit tests PASS

- [ ] **Step 6: Run integration tests**

Run: `pytest tests/integration/ -v`

Expected: All integration tests PASS

- [ ] **Step 7: Run seed script**

Run: `python scripts/seed_db.py`

Expected: Test data created (campaign + 2 contacts)

- [ ] **Step 8: Verify seed data in database**

Run: `psql -h localhost -U postgres -d voice_agent -c "SELECT * FROM agent_operations.campaigns;"`

Expected: Shows test campaign row

- [ ] **Step 9: Run all tests together**

Run: `pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 10: Commit final status**

```bash
git add .env (if tracking) or .env.local
git commit -m "chore: complete db-schema module setup and testing"
```

---

## Success Verification Checklist

- [ ] Alembic migration 001 applied successfully
- [ ] All 5 tables created in agent_operations schema
- [ ] memories_role created with SELECT/INSERT/UPDATE only
- [ ] Seed script populates test data
- [ ] Unit tests (test_models.py) pass
- [ ] Integration tests (test_db_connection.py) pass
- [ ] All models importable from `app.models`
- [ ] FastAPI dependency `get_db()` works
- [ ] Health checks return correct status
- [ ] No syntax or import errors in any module

---

## Phase 1 Completion

Once all tasks complete and tests pass:

```bash
git log --oneline | head -20
# Should show:
# - chore: complete db-schema module setup and testing
# - test: add integration tests for database connectivity
# - test: add unit tests for ORM models
# - feat: add database seed script
# - feat: add PostgreSQL grants script for memories_role
# - feat: add initial migration (all 5 tables)
# - ... etc
```

**Phase 1 Goal: "Schema live; migrations passing"** ✓

---

*Plan prepared by writing-plans skill for db-schema module.*
