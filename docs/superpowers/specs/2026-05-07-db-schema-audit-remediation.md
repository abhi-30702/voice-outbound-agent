# Design: DB-Schema Audit & Remediation

**Date:** 2026-05-07  
**Module:** 1 (Database Schema)  
**Status:** In Review  
**Scope:** Audit existing implementation + complete missing pieces  

---

## Executive Summary

The db-schema module has solid foundational work (all 5 ORM models, migrations, seed script, tests). Audit identified **4 security/compliance gaps** and **6 operational completeness gaps** across:

- **Security & Compliance:** Hardcoded credentials, SQL injection vulnerability, pool config, missing DNC query examples
- **Data Integrity:** ✅ Verified good
- **Operational Readiness:** Missing test infrastructure (pytest.ini, conftest.py), .env.example, documentation
- **Testing:** Unit + integration tests exist but lack coverage for role permissions, DNC SQL patterns, parameterized queries

**Remediation Plan:** 2 steps—security fixes first (critical), then operational completeness.

---

## Phase 1: Audit Findings

### Security & Compliance Issues

#### 1. Hardcoded Credentials in alembic.ini (🔴 CRITICAL)
**Location:** `alembic.ini:63`  
**Issue:** `sqlalchemy.url = postgresql://voice_user:changeme@localhost:5432/voice_agent`  
**Risk:** Credentials exposed in version control, not environment-driven  
**Fix:** Read from `DATABASE_URL` env var (already supported in `env.py`)

#### 2. SQL Injection in init_db.py (🔴 CRITICAL)
**Location:** `app/db/init_db.py:23`  
**Issue:** `f"CREATE SCHEMA IF NOT EXISTS {AGENT_OPERATIONS_SCHEMA}"` uses f-string  
**Risk:** Violates CLAUDE.md parameterized-queries-only rule  
**Fix:** Use `text()` with parameterization or safe constant

#### 3. Alembic Pool Config (🟡 MEDIUM)
**Location:** `alembic/env.py:76`  
**Issue:** Uses `NullPool` for online migrations (no connection reuse)  
**Risk:** Poor performance, excessive connection churn during migrations  
**Fix:** Use `QueuePool` with reasonable pool_size for non-migration async paths

#### 4. Missing DNC Query Examples (🟡 MEDIUM)
**Location:** No `app/db/queries.py` or query helpers  
**Issue:** CLAUDE.md mandates "DNC check MUST be in SQL (NOT EXISTS), never application-level"  
**Risk:** Developers may implement DNC checks incorrectly in future modules  
**Fix:** Create `app/db/queries.py` with documented parameterized NOT EXISTS pattern

---

### Data Integrity Verification ✅

**All verified good:**
- Column types match migration ↔ models (JSONB, String, Enum, DateTime, UUID)
- Constraints enforced (NOT NULL, UNIQUE, FK relationships)
- Indexes on queryable columns (phone_number, status, created_at, call_id)
- JSONB defaults properly configured

---

### Operational Readiness Gaps

#### 1. Missing pytest.ini (🟡 MEDIUM)
**Issue:** No pytest configuration; tests may not auto-discover, async fixtures may not work  
**Impact:** CI/local runs may fail or behave unexpectedly  
**Solution:** Create `pytest.ini` with async mode + discovery rules

#### 2. Missing conftest.py (🟡 MEDIUM)
**Issue:** No shared pytest fixtures; async session setup not centralized  
**Impact:** Integration tests may not isolate properly; database state leaks between tests  
**Solution:** Create `tests/conftest.py` with:
  - `@pytest_asyncio.fixture` for async engine
  - Transactional rollback isolation per test
  - Test database seeding/cleanup hooks

#### 3. Missing .env.example (🟡 MEDIUM)
**Issue:** New developers don't know what env vars to set  
**Impact:** Onboarding friction, config errors  
**Solution:** Create `.env.example` with all required + optional vars

#### 4. Seed Script Robustness (🟡 MEDIUM)
**Issue:** `scripts/seed_db.py` doesn't call `create_tables()` first  
**Risk:** Running seed before migrations fails silently  
**Fix:** Add guard: call `create_tables()` at start, handle idempotent re-runs

#### 5. Missing Documentation (🟡 MEDIUM)
**Issue:** No `app/db/README.md` explaining setup, pooling, testing  
**Impact:** Future developers don't know how to use the layer  
**Solution:** Create README with:
  - Connection string format
  - Pool configuration guide
  - Testing setup + running tests
  - Common queries (DNC check, lead fetch, etc.)

#### 6. Incomplete Test Coverage
**Missing tests:**
  - Role permissions verification (does `memories_role` have correct grants?)
  - DNC SQL pattern integration test (actual NOT EXISTS query)
  - Query parameterization verification
  - Seed script idempotency test

---

## Phase 2: Remediation Strategy

### Step 1: Security Fixes (CRITICAL) 🔴

**1.1 Fix alembic.ini Hardcoded Credentials**
- Remove hardcoded `sqlalchemy.url`
- Rely on `env.py` reading `DATABASE_URL` environment variable
- Update `alembic.ini` comment to document this

**1.2 Fix init_db.py SQL Injection**
- Replace f-string with parameterized `text()` or safe constant reference
- Use `AGENT_OPERATIONS_SCHEMA` constant (already defined)

**1.3 Improve Alembic Pool Configuration**
- For offline migrations: keep `NullPool` (no connection needed)
- For online migrations: use `QueuePool` with pool_size=5, max_overflow=10
- Document rationale in comments

**1.4 Create app/db/queries.py**
- Implement `check_dnc(phone_number: str)` helper
- Show parameterized NOT EXISTS pattern:
  ```python
  SELECT EXISTS (
    SELECT 1 FROM agent_operations.dnc_registry
    WHERE phone_number = %s
  )
  ```
- Add examples for other common queries (lead by campaign, pending calls, etc.)
- All use parameterized queries with bound params

---

### Step 2: Operational Completeness (IMPORTANT) 🟡

**2.1 Create pytest.ini**
- Enable asyncio mode (`asyncio_mode = auto`)
- Configure test discovery (`testpaths = tests`)
- Set markers for unit vs integration tests

**2.2 Create tests/conftest.py**
- AsyncSession fixture with test database isolation
- Automatic rollback per test
- Seed data hooks (optional)

**2.3 Create .env.example**
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/voice_agent
SQLALCHEMY_ECHO=false
POOL_SIZE=10
MAX_OVERFLOW=20
```

**2.4 Improve scripts/seed_db.py**
- Add guard to call `create_tables()` before seeding
- Wrap in try/except for idempotent reruns
- Log clearer output (already good, minor improvements)

**2.5 Create app/db/README.md**
- Connection string format
- Environment variables
- Pool tuning guidance
- Testing locally (run migrations, seed, pytest)
- Common query patterns
- Role permissions reference

**2.6 Expand Integration Tests**
- Add test: `test_memories_role_has_correct_grants()`
  - Query `information_schema.role_table_grants`
  - Verify SELECT, INSERT, UPDATE on all tables
  - Verify no DELETE privilege
  
- Add test: `test_dnc_check_query_succeeds()`
  - Use `check_dnc()` helper from `app/db/queries.py`
  - Insert test phone in DNC registry
  - Assert query returns True
  - Assert non-DNC phone returns False
  
- Add test: `test_seed_idempotency()`
  - Run seed script once, assert counts
  - Run seed script again, assert counts unchanged
  - Verify no duplicate records

---

## Phase 3: Implementation Order

1. **Fix alembic.ini** (2 min)
2. **Fix init_db.py** (2 min)
3. **Fix alembic/env.py pool config** (3 min)
4. **Create app/db/queries.py** with DNC helper (5 min)
5. **Create pytest.ini** (2 min)
6. **Create tests/conftest.py** (5 min)
7. **Create .env.example** (1 min)
8. **Improve scripts/seed_db.py** (3 min)
9. **Create app/db/README.md** (5 min)
10. **Expand tests/integration/test_db_connection.py** (10 min)
11. **Run full test suite** (5 min)
12. **Git commit** (1 min)

**Total: ~45 minutes**

---

## Phase 4: Success Criteria

After implementation:

- ✅ No hardcoded credentials in version control
- ✅ All SQL queries use parameterized/safe patterns (no f-strings for SQL)
- ✅ pytest.ini + conftest.py enable reliable async test execution
- ✅ .env.example documents all configuration
- ✅ DNC query helper exists + demonstrates parameterized NOT EXISTS
- ✅ Integration tests verify role permissions + DNC patterns
- ✅ Seed script runs safely and idempotently
- ✅ Developer documentation (app/db/README.md) covers setup + testing
- ✅ All tests pass (unit + integration)
- ✅ Code adheres to CLAUDE.md security rules

---

## Files to Create / Modify

### Create (New)
- `app/db/queries.py` — DNC check + common query helpers
- `app/db/README.md` — Developer documentation
- `pytest.ini` — pytest configuration
- `tests/conftest.py` — async fixtures + test isolation
- `.env.example` — environment variable reference

### Modify (Existing)
- `alembic.ini` — Remove hardcoded URL
- `app/db/init_db.py` — Fix SQL injection vulnerability
- `alembic/env.py` — Improve pool configuration
- `scripts/seed_db.py` — Add create_tables() guard
- `tests/integration/test_db_connection.py` — Add role + DNC + idempotency tests

---

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|-----------|
| Removing hardcoded URL from alembic.ini | Low | env.py already reads env var; alembic.ini comment explains |
| Changing init_db.py SQL | Low | Using safe constant, not user input |
| Adding pool config to alembic | Low | Only affects migration mode; documented clearly |
| New test fixtures in conftest.py | Low | Standard pytest patterns; isolated per test |
| Adding queries.py helpers | None | New file, no existing code affected |

---

## Timeline

**Estimate:** 45–60 minutes (implementation + testing + commit)

---

*Design prepared by Claude Code brainstorming skill; approved for implementation.*
