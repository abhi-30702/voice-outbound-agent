# Database Layer (`app/db/`)

This module provides async SQLAlchemy infrastructure for voice-outbound-agent. It includes:

- Async connection management and session factories
- FastAPI dependency injection for routes
- Health checks and readiness probes
- Parameterized query helpers for security

## Connection Setup

### Environment Variables

Create a `.env` file (or set environment variables) with:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/voice_agent
SQLALCHEMY_ECHO=false  # Log SQL statements (useful for debugging)
POOL_SIZE=10           # Connection pool size
MAX_OVERFLOW=20        # Overflow connections
```

See `.env.example` for all available options.

### Connection String Format

PostgreSQL async connection strings use `asyncpg`:

```
postgresql+asyncpg://user:password@host:port/database
```

**Example:** `postgresql+asyncpg://postgres:mypassword@localhost:5432/voice_agent`

## Database Initialization

### Create Schema and Tables

For local development or testing:

```bash
python -c "
import asyncio
from app.db.init_db import create_tables
asyncio.run(create_tables())
print('✓ Schema and tables created')
"
```

### Seed Test Data

```bash
python scripts/seed_db.py
```

This creates:
- One test campaign (`Test Campaign`, status=DRAFT)
- Two test leads:
  - DNC lead: `+919876543210` (in DNC registry)
  - Clean lead: `+919876543211` (not in DNC registry)

Script is idempotent; safe to run multiple times.

### Apply Migrations

If using Alembic migrations:

```bash
# Check migration status
alembic current

# Apply pending migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "description"
```

## Connection Pooling

### Configuration

Pool settings are in `app/core/settings.py` and `.env`:

- `POOL_SIZE=10` — Number of persistent connections to maintain
- `MAX_OVERFLOW=20` — Additional connections allowed beyond pool size

For **local development:** Default values (10 / 20) are fine.

For **production:** Tune based on:
- Expected concurrent requests
- Long-running operations (e.g., report generation)
- Database server connection limits

**Rule of thumb:** `POOL_SIZE = (expected_concurrency / 2)`, `MAX_OVERFLOW = POOL_SIZE`

### Async Engine

The async engine is created once at app startup:

```python
from app.db.session import get_engine

engine = await get_engine()  # Reuses singleton
```

Do NOT create multiple engines.

## Using in FastAPI Routes

### Basic Usage

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.dependencies import get_db
from app.models import Campaign

router = APIRouter()

@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch a campaign by ID."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404)
    return campaign
```

The `get_db` dependency automatically provides a fresh session per request and cleans it up.

### Parameterized Queries

ALWAYS use parameterized queries. See `app/db/queries.py` for examples.

**DO THIS:**
```python
from sqlalchemy import text

result = await session.execute(
    text("SELECT * FROM agent_operations.leads WHERE campaign_id = :campaign_id"),
    {"campaign_id": campaign_id}
)
```

**NEVER DO THIS:**
```python
# UNSAFE: SQL injection vulnerability
result = await session.execute(
    text(f"SELECT * FROM agent_operations.leads WHERE campaign_id = '{campaign_id}'")
)
```

## Common Queries

### Check if Phone is in DNC Registry

```python
from app.db.queries import is_phone_in_dnc

is_dnc = await is_phone_in_dnc(session, "+919876543210")
if is_dnc:
    print("Skip dialing this number")
```

### Get Pending Leads for Campaign (excluding DNC)

```python
from app.db.queries import get_pending_leads_for_campaign

leads = await get_pending_leads_for_campaign(
    session,
    campaign_id="abc-123-def",
    limit=50
)

for lead in leads:
    print(f"Dial {lead['phone_number']} in {lead['timezone']}")
```

### Get Call by ID

```python
from app.db.queries import get_call_by_id

call = await get_call_by_id(session, call_id="xyz-789")
if call:
    print(f"Call status: {call['status']}")
```

## Testing

### Unit Tests

Test ORM models without database:

```bash
pytest tests/unit/test_models.py -v
```

These verify column definitions, indexes, and relationships.

### Integration Tests

Test actual database operations:

```bash
# Set DATABASE_URL to test database
export DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/voice_agent_test

pytest tests/integration/test_db_connection.py -v
```

These verify:
- Schema exists (`agent_operations`)
- All tables created
- Permissions correct (`memories_role`)
- Common queries work
- DNC check pattern works

### Running All Tests

```bash
# Unit + integration
pytest tests/ -v

# Only fast tests (unit)
pytest tests/unit/ -v

# Only integration tests
pytest tests/integration/ -v
```

## PostgreSQL Grants

The `memories_role` role is used by the LLM for read-only + structured extraction access.

Grants applied via `scripts/grants.sql`:

```bash
psql -h localhost -U postgres voice_agent < scripts/grants.sql
```

**Permissions:**
- `SELECT` on all tables
- `INSERT, UPDATE` on campaigns, leads, call_logs, call_transcripts
- `SELECT` only on dnc_registry (read-only compliance check)
- No `DELETE`, `DROP`, or `CREATE` privileges

Verify grants:

```sql
SELECT * FROM information_schema.role_table_grants
WHERE grantee = 'memories_role' AND table_schema = 'agent_operations';
```

## Health Checks

### Connectivity Check

```python
from app.db.init_db import check_db_connectivity

is_healthy = await check_db_connectivity()
print("DB healthy" if is_healthy else "DB unreachable")
```

### Migration Status

```python
from app.db.init_db import check_migration_status

version = await check_migration_status()
print(f"Migration version: {version or 'Not migrated'}")
```

### Readiness Probe

```python
from app.db.init_db import get_db_readiness_probe

probe = await get_db_readiness_probe()
# Returns: {"status": "ready" | "not_ready", "connectivity": bool, "migration_version": str | None}
```

Use in FastAPI health endpoint:

```python
@router.get("/health/db")
async def health_db():
    probe = await get_db_readiness_probe()
    status_code = 200 if probe["status"] == "ready" else 503
    return JSONResponse(probe, status_code=status_code)
```

## Architecture Decisions

### Schema Scoping

All tables are in the `agent_operations` schema (not `public`). This isolates application data from system tables.

### Mixins

All models inherit:
- `UUIDPrimaryKeyMixin` — UUID primary keys with auto-generation
- `TimestampMixin` — `created_at`, `updated_at` timestamps (auto-managed)

### Enums vs VARCHAR

**PostgreSQL Enums** used for:
- `campaign_status` (campaign.py)
- `contact_status` (contact.py)
- `call_status` (call.py)
- `dnc_source` (dnc_entry.py)

**VARCHAR** used for:
- `sentiment` (transcript.py) — rapidly changing AI metadata; enum overkill

### Hard Delete Only

Currently, no soft delete. If needed in future, add `deleted_at: TIMESTAMPTZ | None` to specific models.

---

*Generated by Claude Code for voice-outbound-agent Phase 1 (DB-Schema module).*
