# Evals Session Design — TASK-011
**Date:** 2026-05-10
**Scope:** `tests/evals/` only
**Stack:** Python 3.13, pytest, pytest-asyncio, locust, freezegun, Alembic, PostgreSQL 16

---

## 1. Goal

Build a self-contained eval suite under `tests/evals/` that:
- Validates the three hard compliance rules from PRD Section 12 (DNC, CPS, timezone gate)
- Verifies structured output schema correctness (PRD Section 10)
- Confirms webhook HMAC security at the HTTP layer
- Provides a load test measuring peak CPS under 1000 mock leads
- Provides a standalone KPI reporting script for PRD Section 11 metrics

---

## 2. Directory Structure

```
tests/evals/
├── conftest.py                     # real-DB fixtures (Alembic + SAVEPOINT)
├── test_dnc_regression.py          # 100 leads / 10 DNC → 0 DNC dialed
├── test_worker_rate_limit.py       # 10 leads, mock Retell → CPS ≤ 1.0
├── test_timezone_gate.py           # 5 timezones → only in-hours leads dialed
├── test_structured_output.py       # 3 transcripts → ExtractionResult schema valid
├── test_signature_verification.py  # HTTP ASGI → valid=200 / tampered=401
├── locustfile.py                   # 1000 mock leads → peak CPS < 1.1
└── kpi_check.py                    # standalone script → prints all KPI table
```

---

## 3. Test Matrix

| File | Needs real DB | Pass criteria |
|---|---|---|
| `test_dnc_regression` | Yes (PostgreSQL) | 0 of 100 DNC-listed leads returned by `_fetch_pending_leads` |
| `test_worker_rate_limit` | No (mock session) | elapsed ≥ 9.0s for 10 calls; `create_call` called exactly 10× |
| `test_timezone_gate` | No (pure unit) | only leads within 08:00–21:00 local time pass `is_within_calling_hours` |
| `test_structured_output` | No (mock Anthropic) | `ExtractionResult.model_validate()` passes for all 3 transcripts; `dnc_requested=True` only for dnc_request case |
| `test_signature_verification` | No (mock session/redis) | valid HMAC → 200; tampered body → 401 |
| `locustfile` | No (mock Retell) | `max_cps < 1.1` across all 1-second windows over 1000 dispatches |
| `kpi_check` | Yes (read-only query) | prints formatted KPI table; exits 1 if any KPI breaches alert threshold |

---

## 4. Real-DB Fixture Design (`conftest.py`)

### Constraints
- **No `pytest-xdist` parallelism.** SAVEPOINT patterns become unstable under shared parallel execution with async SQLAlchemy. The evals conftest documents this explicitly. Run with `pytest tests/evals/` (no `-n` flag).
- **Alembic migrations, not `create_all`.** The `db_engine` fixture runs `alembic upgrade head` via subprocess so the real migration path is exercised, not a synthetic schema.

### Fixtures

```
db_engine  [session-scoped]
  - creates AsyncEngine from DATABASE_URL
  - runs: subprocess.run(["alembic", "upgrade", "head"])
  - yields engine
  - teardown: subprocess.run(["alembic", "downgrade", "base"]) then engine.dispose()

db_session  [function-scoped]
  - opens a connection from db_engine
  - begins a transaction
  - begins a SAVEPOINT (nested transaction)
  - yields AsyncSession bound to the SAVEPOINT connection
  - teardown: rolls back to SAVEPOINT → no data persists between tests
```

Only `test_dnc_regression` and `kpi_check.py` consume real-DB fixtures.

---

## 5. Individual Test Designs

### `test_dnc_regression.py`
- Insert 90 `Contact` rows (status=pending, unique E.164 numbers) via `db_session`
- Insert 10 `DNCEntry` rows with matching phone numbers
- Call `worker._fetch_pending_leads(session)` directly (no Retell mock needed)
- Assert: `len({c.phone_number for c in result} & dnc_phones) == 0`
- Assert: `len(result) == 90`

### `test_worker_rate_limit.py`
- Build 10 in-memory `Contact` objects (no DB)
- Patch `RetellClient.create_call` → `AsyncMock(return_value={"call_id": "x"})`
- Patch session factory to return the 10 leads
- Call `worker.dial_batch()` and record wall-clock elapsed
- Assert: `elapsed >= 9.0` (10 calls with `asyncio.sleep(1.0)` between each)
- Assert: `create_call.call_count == 10`

### `test_timezone_gate.py`
- Use `freezegun.freeze_time("2026-01-15 14:00:00 UTC")` — a fixed Thursday at 14:00 UTC
- 5 leads, one per timezone: `America/New_York` (09:00 ✓), `Europe/London` (14:00 ✓), `Asia/Kolkata` (19:30 ✓), `Australia/Sydney` (01:00 ✗), `Pacific/Auckland` (03:00 ✗)
- Call `is_within_calling_hours(tz)` for each
- Assert: New York, London, Kolkata → True; Sydney, Auckland → False

### `test_structured_output.py`
Three fixture transcripts passed to `_run_analysis()` with mocked Anthropic client:

| Fixture | Expected outcome | `dnc_requested` |
|---|---|---|
| `qualified_transcript` | `call_outcome="interested"` | False |
| `unqualified_transcript` | `call_outcome="not_interested"` | False |
| `dnc_transcript` | `call_outcome="dnc_request"` | True |

Each test calls `ExtractionResult.model_validate(result)` — if schema is invalid, Pydantic raises `ValidationError`.

### `test_signature_verification.py`
Uses `httpx.AsyncClient(transport=ASGITransport(app))` — same pattern as `tests/integration/test_webhook_router.py`.

- `test_valid_sig_returns_200`: construct body + correct HMAC → POST → assert 200
- `test_tampered_body_returns_401`: construct body, flip one byte, use original HMAC → POST → assert 401
- `test_missing_sig_header_returns_401`: POST with no `x-retell-signature` header → assert 401

### `locustfile.py`
- `LocustWorker` class with 1000 pre-built `Contact` objects and a mocked `RetellClient`
- Each task: calls `worker._dispatch_call(mock_session, lead)` and records `time.time()`
- After run: bucket timestamps into 1-second windows; compute `max_cps`
- Assert: `max_cps < 1.1`
- Designed to run as: `locust -f tests/evals/locustfile.py --headless -u 1 -r 1 --run-time 1100s`

### `kpi_check.py`
Standalone `asyncio.run(main())` script. Queries `call_logs` and `call_transcripts`:

| KPI | Query | Alert threshold |
|---|---|---|
| Avg call duration | `AVG(duration_sec)` | < 30s |
| Structured output completion | `COUNT WHERE structured_data IS NOT NULL / total` | < 85% |
| DNC miss rate | cross-join DNC registry with call_logs | any non-zero |
| Call abandon rate | `COUNT WHERE duration_sec < 10 / total` | > 25% |

Prints formatted table, exits 1 if any threshold breached.

| KPI | Query | Target | Alert threshold |
|---|---|---|---|
| Avg call duration | `AVG(duration_sec)` FROM call_logs | > 90s | < 30s |
| Structured output completion | `COUNT structured_data NOT NULL / total` | > 95% | < 85% |
| DNC miss rate | JOIN call_logs with dnc_registry on phone | 0% | any non-zero |
| Call abandon rate | `COUNT duration_sec < 10 / total` | < 15% | > 25% |
| End-to-end response latency | N/A — not in current schema | < 500ms | > 800ms |
| First-5-second detection rate | N/A — not in current schema | < 20% | > 35% |

The two N/A KPIs require additional instrumentation columns in `call_logs` not present in the current schema. `kpi_check.py` will print them as `"requires instrumentation"` rather than a value.

---

## 6. Dependencies to Add

`locust` and `freezegun` are not in `requirements.txt`. They must be added before implementation.

```
freezegun>=1.5.0
locust>=2.29.0
```

---

## 7. PRD Compliance Mapping

| PRD rule | Verified by |
|---|---|
| DNC scrub miss rate = 0% | `test_dnc_regression` |
| 1 CPS hard limit | `test_worker_rate_limit`, `locustfile` |
| Calling hours 08:00–21:00 local | `test_timezone_gate` |
| Structured output > 95% completion | `test_structured_output` |
| HMAC verification on all webhooks | `test_signature_verification` |
| KPI reporting | `kpi_check.py` |
