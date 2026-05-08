# Design: DB-Schema Module (Phase 1)

**Date:** 2026-05-07  
**Module:** 1 (Database Schema)  
**Phase:** 1  
**Status:** Design Approved  

---

## 1. Architecture Overview

The db-schema module establishes a **shared database layer** that all other modules depend on. It implements:

- **Database infrastructure** (`app/db/`) — async SQLAlchemy engine, session factory, FastAPI dependency injection, and health checks
- **ORM Models** (`app/models/`) — five domain entities as SQLAlchemy declarative classes with mixins and indexes
- **Alembic migrations** (`alembic/`) — auto-generated from model changes
- **PostgreSQL grants** (`scripts/grants.sql`) — separate operational SQL, applied outside migration history
- **Seed data** (`scripts/seed_db.py`) — test data for local dev and CI
- **Settings** (`app/core/settings.py`) — centralized environment config

### Security Boundary

The `memories_role` PostgreSQL role is restricted to:
- `SELECT`, `INSERT`, `UPDATE` privileges on tables in `agent_operations` schema
- No `DELETE` privilege (hard-delete constraints)
- No schema ownership, no `CREATE`, no `DROP` privileges
- Least-privilege-only grants

---

## 2. Database Layer Design (`app/db/`)

### `app/db/base.py`

Defines the SQLAlchemy foundation:

- `Base = DeclarativeBase()` — declarative base for all models
- **Mixins** (reusable, inherited by all models):
  - `TimestampMixin`: `created_at`, `updated_at` (TIMESTAMPTZ, auto-managed)
  - `UUIDPrimaryKeyMixin`: `id` as UUID primary key with `gen_random_uuid()` default
- Metadata registry for Alembic auto-detection

### `app/db/session.py`

Manages database connection:

- Async SQLAlchemy engine instantiated from `DATABASE_URL` (from settings)
- `AsyncSessionLocal` factory for session creation
- Connection pooling config (pool_size, max_overflow)
- Lifecycle: engine created at app startup, disposed at shutdown

### `app/db/dependencies.py`

FastAPI integration:

- `async def get_db()` — dependency function yielding AsyncSession
- Usage in routes: `async def my_route(db: AsyncSession = Depends(get_db))`
- Automatic session cleanup via context manager

### `app/db/init_db.py`

Database initialization and health checks:

- `create_tables()` — create schema and tables (for testing/local dev)
- `check_db_connectivity()` — returns bool; verifies connection works
- `check_migration_status()` — returns current Alembic version; verifies migrations applied
- Optional: `get_readiness_probe()` — probe endpoint for Kubernetes/Docker

---

## 3. ORM Models (`app/models/`)

### Naming Convention

- Model class name: PascalCase (e.g., `Contact`, `Call`)
- Table name: snake_case (e.g., `contacts`, `calls`)
- All tables in `agent_operations` schema

### Model Files

#### `campaign.py` → campaigns table

```python
class Campaign:
    id: UUID (PK)
    name: VARCHAR(255) NOT NULL
    status: Enum (draft|active|paused|completed) DEFAULT 'draft'
    prompt_template: JSONB NOT NULL
    llm_config: JSONB NOT NULL
    created_at, updated_at: TIMESTAMPTZ
```

- Index on: `status` (filtering active campaigns)

#### `contact.py` → contacts table (formerly "leads")

```python
class Contact:
    id: UUID (PK)
    phone_number: VARCHAR(20) NOT NULL
    first_name: VARCHAR(100)
    last_name: VARCHAR(100)
    company: VARCHAR(255)
    timezone: VARCHAR(50) NOT NULL (e.g., 'Asia/Kolkata')
    campaign_id: UUID (FK → campaigns.id)
    status: Enum (pending|calling|completed|failed|failed_dnc) DEFAULT 'pending'
    retry_count: INTEGER DEFAULT 0
    next_retry_at: TIMESTAMPTZ
    custom_vars: JSONB
    created_at, updated_at: TIMESTAMPTZ
```

- Indexes on: `phone_number`, `campaign_id`, `status`, `created_at`
- Timezone validation: must be valid IANA timezone or raise error

#### `call.py` → calls table (formerly "call_logs")

```python
class Call:
    id: UUID (PK)
    contact_id: UUID (FK → contacts.id)
    retell_call_id: VARCHAR(255)
    status: Enum (pending|calling|completed|failed) DEFAULT 'pending'
    start_time: TIMESTAMPTZ
    end_time: TIMESTAMPTZ
    duration_sec: INTEGER
    disconnect_reason: VARCHAR(100)
    recording_url: VARCHAR(500)
    created_at, updated_at: TIMESTAMPTZ
```

- Indexes on: `contact_id`, `created_at`, `status`

#### `transcript.py` → call_transcripts table

```python
class Transcript:
    id: UUID (PK)
    call_id: UUID (FK → calls.id) NOT NULL UNIQUE
    raw_transcript: TEXT
    structured_data: JSONB
    sentiment: VARCHAR(50) (positive|neutral|negative)
    created_at, updated_at: TIMESTAMPTZ
```

- Index on: `call_id`

#### `dnc_entry.py` → dnc_registry table (separate, compliance-focused)

```python
class DNCEntry:
    id: UUID (PK)
    phone_number: VARCHAR(20) NOT NULL UNIQUE
    source: VARCHAR(100) (manual|national_dnc|caller_request)
    added_at: TIMESTAMPTZ DEFAULT NOW()
```

- Index on: `phone_number` (UNIQUE, for O(1) pre-dial scrubs)

### Model Design Decisions

**Mixins:** All models inherit `TimestampMixin` and `UUIDPrimaryKeyMixin` to eliminate boilerplate.

**Table args:** Use `__table_args__ = {"schema": "agent_operations"}` (SQLAlchemy-recommended over schema-qualified tablename).

**Enums:** Use PostgreSQL enums for: `campaign_status`, `call_status`, `dnc_source`. Use VARCHAR for: `sentiment`, `disconnect_reason` (rapidly changing AI metadata).

**Soft delete:** Hard delete only. If soft-delete needed in future, add `deleted_at: TIMESTAMPTZ | None = None` column to specific models.

**Foreign keys:** Explicit `ForeignKey` constraints in model definitions; Alembic generates them.

---

## 4. Alembic Migrations

### `alembic/env.py`

Configuration:

- Async SQLAlchemy mode enabled
- `sqlalchemy.url` loaded from `settings.DATABASE_URL`
- `target_metadata = Base.metadata` (Alembic auto-discovers model changes)
- `compare_type = True` (detect type changes)

### `alembic/versions/001_initial_schema.py`

Auto-generated migration:

- Create `agent_operations` schema
- Create all five tables with columns, constraints, indexes
- Reviewable before apply

Run: `alembic revision --autogenerate -m "initial_schema"`

### `scripts/grants.sql` (Separate from Migrations)

Operational SQL, applied after migration 001:

```sql
CREATE ROLE IF NOT EXISTS memories_role;
GRANT USAGE ON SCHEMA agent_operations TO memories_role;
GRANT SELECT, INSERT, UPDATE ON agent_operations.campaigns TO memories_role;
GRANT SELECT, INSERT, UPDATE ON agent_operations.contacts TO memories_role;
GRANT SELECT, INSERT, UPDATE ON agent_operations.calls TO memories_role;
GRANT SELECT, INSERT ON agent_operations.call_transcripts TO memories_role;
GRANT SELECT ON agent_operations.dnc_registry TO memories_role;
-- No DELETE, DROP, CREATE privileges
```

Applied via: `psql -h localhost -U postgres voice_agent < scripts/grants.sql`

**Rationale:** Grants are environment-specific (staging vs prod) and infra-automation-friendly outside migration history.

---

## 5. Seed Data (`scripts/seed_db.py`)

Standalone Python script:

- Uses shared `app/db/session.py` engine for connectivity
- Inserts one test campaign: `name="Test Campaign"`, `status="draft"`
- Inserts two test contacts:
  - Contact 1: phone in `dnc_registry`, status pending (tests DNC filtering)
  - Contact 2: clean contact, status pending (tests normal dial flow)
- Idempotent: checks existence before insert
- Run: `python scripts/seed_db.py`

---

## 6. Configuration (`app/core/settings.py`)

Pydantic settings (environment-based):

```python
class Settings(BaseSettings):
    DATABASE_URL: str  # e.g., 'postgresql+asyncpg://user:pass@localhost/voice_agent'
    SQLALCHEMY_ECHO: bool = False  # Log all SQL if True
    POOL_SIZE: int = 10
    MAX_OVERFLOW: int = 20
```

Loaded from `.env` file.

---

## 7. Testing Strategy

### Integration Test (`tests/integration/test_db_connection.py`)

Requirements:
- Live PostgreSQL database (via Docker or CI service)
- `pytest-asyncio` for async fixtures
- Transactional rollback isolation (each test in its own transaction, rolled back after)

Tests:
- Connectivity check (engine can connect)
- Schema exists (`agent_operations`)
- All five tables created
- `memories_role` exists with correct SELECT/INSERT/UPDATE privileges
- Sample query succeeds

### Unit Test (`tests/unit/test_models.py`)

Requirements:
- Mocked SQLAlchemy session (no database)
- `pytest` + `unittest.mock`

Tests:
- ORM column definitions match schema (type, nullable, defaults)
- Indexes defined correctly
- Foreign key relationships correct
- Mixins applied (timestamp, UUID PK)

No database required; runs in seconds.

---

## 8. Future Layering (Documented, Not Implemented)

To prevent business logic leakage into route handlers:

```
API Routes → Services (business logic) → Repositories (query builders) → ORM Models
```

This layering will be introduced in later modules (dialing-worker, webhook-receiver, etc.).

---

## 9. Health Check / Readiness Probe

`app/db/init_db.py` exposes:

- `check_db_connectivity()` — returns bool
- `check_migration_status()` — returns current Alembic version
- Future: `/health/db` endpoint for Kubernetes probes

---

## 10. Project Structure (Final)

```
D:\Projects\voice-outbound-agent\
├── app/
│   ├── core/
│   │   └── settings.py
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   ├── dependencies.py
│   │   └── init_db.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── campaign.py
│   │   ├── contact.py
│   │   ├── call.py
│   │   ├── transcript.py
│   │   └── dnc_entry.py
│   ├── schemas/    (for Pydantic request/response schemas, future)
│   ├── api/        (for route handlers, future)
│   └── services/   (for business logic, future)
│
├── alembic/
│   ├── env.py
│   ├── script.py_mako
│   └── versions/
│       └── 001_initial_schema.py
│
├── scripts/
│   ├── seed_db.py
│   └── grants.sql
│
├── tests/
│   ├── unit/
│   │   └── test_models.py
│   └── integration/
│       └── test_db_connection.py
│
├── .env                  (local, git-ignored)
├── .env.example
├── alembic.ini
├── CLAUDE.md
├── PRD.md
└── pyproject.toml / requirements.txt
```

---

## 11. Implementation Checklist

1. ✅ Design approved
2. [ ] Alembic init (`alembic init alembic`)
3. [ ] `app/core/settings.py` with DATABASE_URL
4. [ ] `app/db/base.py` with mixins
5. [ ] `app/db/session.py` async engine + sessionmaker
6. [ ] `app/db/dependencies.py` FastAPI get_db()
7. [ ] `app/db/init_db.py` health checks
8. [ ] `app/models/{campaign,contact,call,transcript,dnc_entry}.py`
9. [ ] `alembic/env.py` async + target_metadata
10. [ ] `alembic/versions/001_initial_schema.py` (auto-generated)
11. [ ] `scripts/grants.sql` memory_role permissions
12. [ ] `scripts/seed_db.py` test data
13. [ ] `tests/unit/test_models.py` ORM validation
14. [ ] `tests/integration/test_db_connection.py` live DB test
15. [ ] `pytest tests/` — all pass
16. [ ] Commit with message: `[TASK-001] init: db-schema module (SQLAlchemy + Alembic)`

---

## 12. Success Criteria (Phase 1)

- [ ] PostgreSQL schema `agent_operations` exists with all five tables
- [ ] Alembic migration 001 applies cleanly and is idempotent
- [ ] `memories_role` has SELECT/INSERT/UPDATE only; no DELETE/DROP
- [ ] Seed script populates test data successfully
- [ ] Both integration and unit tests pass
- [ ] Health check endpoints respond correctly
- [ ] Code follows PRD security rules (parameterized queries, no string interpolation)

---

*Document prepared by Claude Code brainstorming skill.*
