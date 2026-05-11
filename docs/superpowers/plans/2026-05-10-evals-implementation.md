# Evals Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `tests/evals/` — a self-contained eval suite with 5 pytest tests, a CPS load tester, and a KPI reporting script covering all PRD Section 11 and 12 compliance rules.

**Architecture:** `tests/evals/` is fully isolated from `tests/unit/` and `tests/integration/`. Real-DB tests (`test_dnc_regression`, `kpi_check.py`) use Alembic migrations + SAVEPOINT rollback. Mock-based tests follow the same patterns as `tests/integration/`. `locustfile.py` and `kpi_check.py` are standalone scripts runnable independently of pytest.

**Tech Stack:** pytest 8.2, pytest-asyncio 0.24 (`asyncio_mode = auto`), freezegun ≥ 1.5, httpx + ASGITransport, SQLAlchemy 2.x AsyncSession, Alembic (subprocess), locust ≥ 2.29 (standalone runner)

---

## File Map

| File | Create / Modify | Purpose |
|---|---|---|
| `requirements.txt` | Modify | Add `freezegun>=1.5.0`, `locust>=2.29.0` |
| `tests/evals/__init__.py` | Create | Empty — enables pytest discovery |
| `tests/evals/conftest.py` | Create | Real-DB fixtures: `db_engine` (session-scoped, Alembic), `db_session` (function-scoped, SAVEPOINT) |
| `tests/evals/test_dnc_regression.py` | Create | Insert 90 clean + 10 DNC leads; assert `_fetch_pending_leads` returns 90, none in DNC |
| `tests/evals/test_worker_rate_limit.py` | Create | 10 mock leads; assert elapsed ≥ 9.0s and `create_call` called 10× |
| `tests/evals/test_timezone_gate.py` | Create | 5 timezones frozen at 14:00 UTC; assert correct in/out-of-hours result |
| `tests/evals/test_structured_output.py` | Create | Mock Anthropic; assert `ExtractionResult.model_validate()` passes for 3 transcripts |
| `tests/evals/test_signature_verification.py` | Create | ASGI client; valid → 200, tampered → 403, missing header → 422 |
| `tests/evals/locustfile.py` | Create | In-process worker, 10 leads with real sleep, assert peak CPS < 1.1 |
| `tests/evals/kpi_check.py` | Create | Standalone script; queries real DB; prints all 6 PRD Section 11 KPIs; exits 1 on breach |

---

## Task 1: Add dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add freezegun and locust**

Open `requirements.txt` and append these two lines:

```
freezegun>=1.5.0
locust>=2.29.0
```

- [ ] **Step 2: Install into the venv**

```powershell
.venv\Scripts\pip install freezegun>=1.5.0 "locust>=2.29.0"
```

Expected: both packages install without errors.

- [ ] **Step 3: Verify imports work**

```powershell
.venv\Scripts\python -c "import freezegun; import locust; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```powershell
git add requirements.txt
git commit -m "chore: add freezegun and locust for TASK-011 evals"
```

---

## Task 2: Scaffold `tests/evals/` and conftest

**Files:**
- Create: `tests/evals/__init__.py`
- Create: `tests/evals/conftest.py`

- [ ] **Step 1: Create empty `__init__.py`**

Create `tests/evals/__init__.py` with no content (empty file).

- [ ] **Step 2: Write `conftest.py`**

Create `tests/evals/conftest.py`:

```python
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
```

- [ ] **Step 3: Verify conftest is discovered**

```powershell
.venv\Scripts\pytest tests/evals/ --collect-only 2>&1 | Select-Object -First 10
```

Expected: no import errors; `0 tests collected` (files not yet created).

- [ ] **Step 4: Commit**

```powershell
git add tests/evals/__init__.py tests/evals/conftest.py
git commit -m "feat: scaffold tests/evals/ with real-DB conftest (TASK-011)"
```

---

## Task 3: DNC regression test (real DB)

**Files:**
- Create: `tests/evals/test_dnc_regression.py`

**Requires:** PostgreSQL running at `DATABASE_URL` (e.g. `docker compose up postgres -d`).

- [ ] **Step 1: Write the test**

Create `tests/evals/test_dnc_regression.py`:

```python
"""DNC regression: 90 clean + 10 DNC leads → _fetch_pending_leads returns 90, 0 from DNC.

Requires a live PostgreSQL instance at DATABASE_URL.
Run: pytest tests/evals/test_dnc_regression.py -v
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.dialing_worker.config import DialerConfig
from app.dialing_worker.worker import DialerWorker
from app.models import Contact, ContactStatus, DNCEntry, DNCSource


@pytest.mark.asyncio
async def test_zero_dnc_leads_dispatched(db_session):
    """SQL NOT EXISTS filters all DNC-listed phones; 90 clean leads returned."""
    past = datetime.utcnow() - timedelta(minutes=5)

    clean_phones = [f"+1555{str(i).zfill(7)}" for i in range(90)]
    dnc_phones = [f"+1999{str(i).zfill(7)}" for i in range(10)]

    for phone in clean_phones + dnc_phones:
        db_session.add(Contact(
            phone_number=phone,
            first_name="Test",
            timezone="America/New_York",
            status=ContactStatus.PENDING,
            next_retry_at=past,
        ))

    for phone in dnc_phones:
        db_session.add(DNCEntry(
            phone_number=phone,
            source=DNCSource.MANUAL,
        ))

    await db_session.flush()   # write within SAVEPOINT — never committed

    with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
        worker = DialerWorker(DialerConfig(retell_api_key="test", batch_size=200))

    result = await worker._fetch_pending_leads(db_session)

    result_phones = {c.phone_number for c in result}
    dnc_set = set(dnc_phones)

    assert len(result) == 90, f"Expected 90 leads, got {len(result)}"
    leaked = result_phones & dnc_set
    assert not leaked, f"DNC leads leaked into results: {leaked}"
```

- [ ] **Step 2: Run it to verify it fails without a DB**

```powershell
.venv\Scripts\pytest tests/evals/test_dnc_regression.py -v
```

Expected: SKIP or ERROR (`alembic upgrade head` fails if no DB), not a false PASS.

- [ ] **Step 3: Start postgres and run again**

```powershell
docker compose up postgres -d
# wait ~5 seconds for healthcheck to pass, then:
.venv\Scripts\pytest tests/evals/test_dnc_regression.py -v
```

Expected:
```
tests/evals/test_dnc_regression.py::test_zero_dnc_leads_dispatched PASSED
```

- [ ] **Step 4: Commit**

```powershell
git add tests/evals/test_dnc_regression.py
git commit -m "feat: add test_dnc_regression — 100-lead SQL NOT EXISTS eval (TASK-011)"
```

---

## Task 4: Worker rate-limit test (mock)

**Files:**
- Create: `tests/evals/test_worker_rate_limit.py`

- [ ] **Step 1: Write the test**

Create `tests/evals/test_worker_rate_limit.py`:

```python
"""Rate-limit eval: 10 leads dispatched → elapsed ≥ 9.0s (asyncio.sleep(1.0) enforced).

No database required — all DB calls are mocked.
Run: pytest tests/evals/test_worker_rate_limit.py -v
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.dialing_worker.config import DialerConfig
from app.dialing_worker.worker import DialerWorker
from app.models import Contact, ContactStatus

LEAD_COUNT = 10


@pytest.mark.asyncio
async def test_1_cps_enforced_over_10_leads():
    """dial_batch with 10 leads must take ≥ 9.0s and call create_call exactly 10 times."""
    config = DialerConfig(retell_api_key="test-key", batch_size=50)

    with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
        worker = DialerWorker(config)

    worker.retell_client.create_call = AsyncMock(return_value={"call_id": "c1"})

    campaign_id = uuid4()
    leads = [
        Contact(
            id=uuid4(),
            phone_number=f"+1555{str(i).zfill(7)}",
            first_name=f"Lead{i}",
            timezone="America/New_York",
            campaign_id=campaign_id,
            status=ContactStatus.PENDING,
        )
        for i in range(LEAD_COUNT)
    ]

    # _fetch_pending_leads uses session.execute(text(...)).fetchall()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        (l.id, l.phone_number, l.first_name, None, None,
         l.timezone, l.campaign_id, "pending", 0, None, None, None, None)
        for l in leads
    ]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    # _dispatch_call uses session.get(Campaign, campaign_id)
    mock_session.get = AsyncMock(return_value=MagicMock(
        name="Test Campaign",
        llm_config={"retell_agent_id": "agent_eval"},
    ))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    worker.session_factory = MagicMock(return_value=cm)

    with patch("app.dialing_worker.worker.is_within_calling_hours", return_value=True):
        start = time.monotonic()
        await worker.dial_batch()
        elapsed = time.monotonic() - start

    assert worker.retell_client.create_call.call_count == LEAD_COUNT, (
        f"Expected {LEAD_COUNT} calls, got {worker.retell_client.create_call.call_count}"
    )
    assert elapsed >= 9.0, f"1 CPS not enforced: elapsed={elapsed:.2f}s for {LEAD_COUNT} leads"
    assert elapsed < 15.0, f"Worker too slow: elapsed={elapsed:.2f}s"
```

- [ ] **Step 2: Run the test (takes ~10 seconds)**

```powershell
.venv\Scripts\pytest tests/evals/test_worker_rate_limit.py -v
```

Expected:
```
tests/evals/test_worker_rate_limit.py::test_1_cps_enforced_over_10_leads PASSED
```

- [ ] **Step 3: Commit**

```powershell
git add tests/evals/test_worker_rate_limit.py
git commit -m "feat: add test_worker_rate_limit — 1 CPS eval over 10 mock leads (TASK-011)"
```

---

## Task 5: Timezone gate test (freezegun)

**Files:**
- Create: `tests/evals/test_timezone_gate.py`

- [ ] **Step 1: Write the test**

Create `tests/evals/test_timezone_gate.py`:

```python
"""Timezone gate eval: 5 timezones frozen at 2026-01-15 14:00 UTC.

Expected results at that moment:
  America/New_York  → 09:00 EST  → IN  hours ✓
  Europe/London     → 14:00 GMT  → IN  hours ✓
  Asia/Kolkata      → 19:30 IST  → IN  hours ✓
  Australia/Sydney  → 01:00 AEDT → OUT of hours ✗
  Pacific/Auckland  → 03:00 NZDT → OUT of hours ✗

No database required.
Run: pytest tests/evals/test_timezone_gate.py -v
"""
import pytest
from freezegun import freeze_time

from app.dialing_worker.timezone_utils import is_within_calling_hours

FROZEN = "2026-01-15 14:00:00"


@freeze_time(FROZEN)
class TestTimezoneGate:

    def test_new_york_in_hours(self):
        assert is_within_calling_hours("America/New_York") is True

    def test_london_in_hours(self):
        assert is_within_calling_hours("Europe/London") is True

    def test_kolkata_in_hours(self):
        assert is_within_calling_hours("Asia/Kolkata") is True

    def test_sydney_out_of_hours(self):
        assert is_within_calling_hours("Australia/Sydney") is False

    def test_auckland_out_of_hours(self):
        assert is_within_calling_hours("Pacific/Auckland") is False
```

- [ ] **Step 2: Run the test**

```powershell
.venv\Scripts\pytest tests/evals/test_timezone_gate.py -v
```

Expected:
```
tests/evals/test_timezone_gate.py::TestTimezoneGate::test_new_york_in_hours PASSED
tests/evals/test_timezone_gate.py::TestTimezoneGate::test_london_in_hours PASSED
tests/evals/test_timezone_gate.py::TestTimezoneGate::test_kolkata_in_hours PASSED
tests/evals/test_timezone_gate.py::TestTimezoneGate::test_sydney_out_of_hours PASSED
tests/evals/test_timezone_gate.py::TestTimezoneGate::test_auckland_out_of_hours PASSED
```

If any fail: check `is_within_calling_hours` signature — it may require `start_hour`/`end_hour` keyword args. If so, call it as `is_within_calling_hours("America/New_York", start_hour=8, end_hour=21)`.

- [ ] **Step 3: Commit**

```powershell
git add tests/evals/test_timezone_gate.py
git commit -m "feat: add test_timezone_gate — 5-timezone freezegun eval (TASK-011)"
```

---

## Task 6: Structured output schema test (mock Anthropic)

**Files:**
- Create: `tests/evals/test_structured_output.py`

- [ ] **Step 1: Write the test**

Create `tests/evals/test_structured_output.py`:

```python
"""Structured output eval: mock Anthropic tool_use response → ExtractionResult validates.

Tests all three outcome types: interested, not_interested, dnc_request.
dnc_requested must be True only for dnc_request outcome.
No database required.
Run: pytest tests/evals/test_structured_output.py -v
"""
from unittest.mock import MagicMock, patch

import pytest

from app.post_call_analysis.schemas import ExtractionResult
from app.post_call_analysis.worker import _call_claude

QUALIFIED = (
    "Agent: Hi, this is Sarah. Is this the right contact?\n"
    "User: Yes speaking.\n"
    "Agent: Great. We have office space matching your requirements. "
    "Budget is approved for Q3?\n"
    "User: Yes budget is ready. Call me back Tuesday."
)

UNQUALIFIED = (
    "Agent: Hi, this is Sarah from Fidelitus.\n"
    "User: Not interested. Goodbye."
)

DNC = (
    "Agent: Hi, this is Sarah.\n"
    "User: Stop calling me. Remove me from your list right now."
)


def _mock_client(outcome: str, dnc: bool) -> MagicMock:
    """Build a mock anthropic.Anthropic client that returns a tool_use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {
        "call_outcome": outcome,
        "callback_time": None,
        "objections_raised": [],
        "next_action": "Follow up",
        "summary": "Test summary.",
        "sentiment_reason": "Neutral tone.",
        "lead_temperature": "warm",
        "sentiment": "neutral",
        "dnc_requested": dnc,
    }
    response = MagicMock()
    response.content = [tool_block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


@pytest.mark.parametrize("transcript,outcome,dnc_expected", [
    (QUALIFIED, "interested", False),
    (UNQUALIFIED, "not_interested", False),
    (DNC, "dnc_request", True),
])
def test_extraction_schema_valid(transcript, outcome, dnc_expected):
    """_call_claude returns ExtractionResult that passes model_validate for every outcome type."""
    mock_client = _mock_client(outcome, dnc_expected)

    with patch("app.post_call_analysis.worker.anthropic.Anthropic", return_value=mock_client):
        result = _call_claude(transcript)

    validated = ExtractionResult.model_validate(result.model_dump())
    assert validated.call_outcome == outcome
    assert validated.dnc_requested == dnc_expected
```

- [ ] **Step 2: Run the test**

```powershell
.venv\Scripts\pytest tests/evals/test_structured_output.py -v
```

Expected:
```
tests/evals/test_structured_output.py::test_extraction_schema_valid[...-interested-False] PASSED
tests/evals/test_structured_output.py::test_extraction_schema_valid[...-not_interested-False] PASSED
tests/evals/test_structured_output.py::test_extraction_schema_valid[...-dnc_request-True] PASSED
```

- [ ] **Step 3: Commit**

```powershell
git add tests/evals/test_structured_output.py
git commit -m "feat: add test_structured_output — schema eval for 3 transcript types (TASK-011)"
```

---

## Task 7: Signature verification test (ASGI)

**Files:**
- Create: `tests/evals/test_signature_verification.py`

Note: the webhook dependency raises **HTTP 403** (not 401) on bad HMAC. Missing the header entirely returns **422** (FastAPI validation error). These are the actual codes in `app/webhook_receiver/dependencies.py`.

- [ ] **Step 1: Write the test**

Create `tests/evals/test_signature_verification.py`:

```python
"""Signature verification eval: ASGI client; valid → 200, tampered → 403, missing → 422.

Uses ASGITransport (no lifespan triggered). app.state is injected manually.
No database required.
Run: pytest tests/evals/test_signature_verification.py -v
"""
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.webhook_receiver.main import app

TEST_SECRET = "eval-hmac-secret"


def _sig(body: bytes, secret: str = TEST_SECRET) -> str:
    return hmac.new(
        key=secret.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()


def _body(call_id: str = "eval_001") -> bytes:
    return json.dumps({"event": "call_started", "call_id": call_id}).encode()


@pytest_asyncio.fixture
async def client():
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=0)
    mock_redis.setex = AsyncMock()

    mock_session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    app.state.redis = mock_redis
    app.state.session_factory = MagicMock(return_value=session_cm)

    with patch("app.core.settings.settings.RETELL_WEBHOOK_SECRET", TEST_SECRET):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c

    app.state._state.clear()


@pytest.mark.asyncio
async def test_valid_signature_returns_200(client):
    body = _body("eval_valid")
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()):
        r = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _sig(body), "content-type": "application/json"},
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_tampered_body_returns_403(client):
    original = _body("eval_tamper")
    sig = _sig(original)
    tampered = original[:-1] + b"X"   # flip last byte; signature no longer matches

    r = await client.post(
        "/webhook",
        content=tampered,
        headers={"x-retell-signature": sig, "content-type": "application/json"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_missing_signature_header_returns_422(client):
    body = _body("eval_nosig")
    r = await client.post(
        "/webhook",
        content=body,
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run the test**

```powershell
.venv\Scripts\pytest tests/evals/test_signature_verification.py -v
```

Expected:
```
tests/evals/test_signature_verification.py::test_valid_signature_returns_200 PASSED
tests/evals/test_signature_verification.py::test_tampered_body_returns_403 PASSED
tests/evals/test_signature_verification.py::test_missing_signature_header_returns_422 PASSED
```

- [ ] **Step 3: Commit**

```powershell
git add tests/evals/test_signature_verification.py
git commit -m "feat: add test_signature_verification — ASGI HMAC eval (TASK-011)"
```

---

## Task 8: Load test (`locustfile.py`)

**Files:**
- Create: `tests/evals/locustfile.py`

Uses 10 leads with real `asyncio.sleep(1.0)` (takes ~10s). Timestamps are recorded per dispatch and bucketed into 1-second windows to compute peak CPS.

- [ ] **Step 1: Write the script**

Create `tests/evals/locustfile.py`:

```python
"""CPS load test for DialerWorker.

Dispatches LEAD_COUNT leads through the worker's dial_batch loop.
Records a timestamp per create_call invocation, buckets into 1-second
windows, and asserts peak CPS < 1.1.

Run: python tests/evals/locustfile.py
     (takes ~10 seconds for LEAD_COUNT=10)
"""
import asyncio
import sys
import time
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.dialing_worker.config import DialerConfig
from app.dialing_worker.worker import DialerWorker
from app.models import Contact, ContactStatus

LEAD_COUNT = 10


def _build_leads(n: int, campaign_id) -> list[Contact]:
    return [
        Contact(
            id=uuid4(),
            phone_number=f"+1555{str(i).zfill(7)}",
            first_name=f"Lead{i}",
            timezone="America/New_York",
            campaign_id=campaign_id,
            status=ContactStatus.PENDING,
        )
        for i in range(n)
    ]


def _compute_max_cps(timestamps: list[float]) -> float:
    if len(timestamps) < 2:
        return float(len(timestamps))
    t0 = timestamps[0]
    buckets: dict[int, int] = defaultdict(int)
    for ts in timestamps:
        buckets[int(ts - t0)] += 1
    return float(max(buckets.values()))


async def run_load_test(lead_count: int = LEAD_COUNT) -> dict:
    timestamps: list[float] = []
    campaign_id = uuid4()

    with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
        worker = DialerWorker(DialerConfig(retell_api_key="load-test"))

    async def tracked_create_call(*args, **kwargs):
        timestamps.append(time.monotonic())
        return {"call_id": str(uuid4())}

    worker.retell_client.create_call = tracked_create_call

    leads = _build_leads(lead_count, campaign_id)

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        (l.id, l.phone_number, l.first_name, None, None,
         l.timezone, l.campaign_id, "pending", 0, None, None, None, None)
        for l in leads
    ]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.get = AsyncMock(return_value=MagicMock(
        name="Load Test Campaign",
        llm_config={"retell_agent_id": "agent_load"},
    ))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    worker.session_factory = MagicMock(return_value=cm)

    with patch("app.dialing_worker.worker.is_within_calling_hours", return_value=True):
        await worker.dial_batch()

    return {
        "lead_count": lead_count,
        "dispatched": len(timestamps),
        "max_cps": _compute_max_cps(timestamps),
    }


if __name__ == "__main__":
    print(f"Running CPS load test: {LEAD_COUNT} leads...")
    result = asyncio.run(run_load_test(LEAD_COUNT))

    print(f"  Dispatched : {result['dispatched']}")
    print(f"  Peak CPS   : {result['max_cps']:.2f}")

    if result["dispatched"] != result["lead_count"]:
        print(f"FAIL: expected {result['lead_count']} dispatches, got {result['dispatched']}")
        sys.exit(1)

    if result["max_cps"] >= 1.1:
        print(f"FAIL: peak CPS {result['max_cps']:.2f} >= 1.1")
        sys.exit(1)

    print("PASS: peak CPS < 1.1")
```

- [ ] **Step 2: Run the load test (takes ~10 seconds)**

```powershell
.venv\Scripts\python tests/evals/locustfile.py
```

Expected:
```
Running CPS load test: 10 leads...
  Dispatched : 10
  Peak CPS   : 1.00
PASS: peak CPS < 1.1
```

- [ ] **Step 3: Commit**

```powershell
git add tests/evals/locustfile.py
git commit -m "feat: add locustfile.py — CPS load eval for DialerWorker (TASK-011)"
```

---

## Task 9: KPI check script

**Files:**
- Create: `tests/evals/kpi_check.py`

Standalone script. Requires PostgreSQL at `DATABASE_URL` with real call data. Exits 1 if any measurable KPI breaches its PRD Section 11 alert threshold.

- [ ] **Step 1: Write the script**

Create `tests/evals/kpi_check.py`:

```python
"""KPI reporting script — PRD Section 11.

Queries agent_operations schema and prints all 6 KPIs.
Exits 1 if any measurable KPI breaches its alert threshold.

Run: python tests/evals/kpi_check.py
Requires: DATABASE_URL pointing to a seeded PostgreSQL instance.
"""
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.settings import settings

THRESHOLDS = {
    "avg_duration_sec":       {"alert": 30,   "direction": "min"},
    "structured_output_pct":  {"alert": 85.0, "direction": "min"},
    "dnc_miss_count":         {"alert": 1,    "direction": "max"},
    "abandon_rate_pct":       {"alert": 25.0, "direction": "max"},
}


async def fetch_kpis(session: AsyncSession) -> dict:
    kpis = {}

    r = await session.execute(text(
        "SELECT AVG(duration_sec) FROM agent_operations.call_logs "
        "WHERE duration_sec IS NOT NULL"
    ))
    kpis["avg_duration_sec"] = float(r.scalar() or 0)

    r = await session.execute(text("""
        SELECT
            COUNT(CASE WHEN structured_data IS NOT NULL THEN 1 END)
            * 100.0 / NULLIF(COUNT(*), 0)
        FROM agent_operations.call_transcripts
    """))
    kpis["structured_output_pct"] = float(r.scalar() or 0)

    r = await session.execute(text("""
        SELECT COUNT(*)
        FROM agent_operations.call_logs cl
        JOIN agent_operations.leads l   ON l.id = cl.lead_id
        JOIN agent_operations.dnc_registry d ON d.phone_number = l.phone_number
    """))
    kpis["dnc_miss_count"] = int(r.scalar() or 0)

    r = await session.execute(text("""
        SELECT
            COUNT(CASE WHEN duration_sec < 10 THEN 1 END)
            * 100.0 / NULLIF(COUNT(*), 0)
        FROM agent_operations.call_logs
        WHERE duration_sec IS NOT NULL
    """))
    kpis["abandon_rate_pct"] = float(r.scalar() or 0)

    return kpis


def _status(key: str, value: float) -> str:
    cfg = THRESHOLDS[key]
    if cfg["direction"] == "min":
        return "PASS" if value >= cfg["alert"] else "FAIL"
    return "PASS" if value <= cfg["alert"] else "FAIL"


def print_report(kpis: dict) -> bool:
    header = f"{'KPI':<38} {'Value':>10} {'Target':>10} {'Alert':>10} {'Status':>6}"
    print("\n" + header)
    print("-" * len(header))

    rows = [
        ("Avg call duration (s)",         kpis["avg_duration_sec"],      "> 90s",  "< 30s",  "avg_duration_sec"),
        ("Structured output completion %", kpis["structured_output_pct"], "> 95%",  "< 85%",  "structured_output_pct"),
        ("DNC miss count",                 kpis["dnc_miss_count"],        "= 0",    ">= 1",   "dnc_miss_count"),
        ("Call abandon rate %",            kpis["abandon_rate_pct"],      "< 15%",  "> 25%",  "abandon_rate_pct"),
        ("E2E response latency (ms)",      None,                           "< 500ms","800ms",  None),
        ("First-5s detection rate %",      None,                           "< 20%",  "> 35%",  None),
    ]

    all_pass = True
    for label, value, target, alert, key in rows:
        if key is None:
            print(f"  {label:<36} {'N/A':>10} {target:>10} {alert:>10} {'N/A':>6}")
            print(f"    └─ requires additional instrumentation columns in call_logs")
            continue
        status = _status(key, float(value))
        if status == "FAIL":
            all_pass = False
        print(f"  {label:<36} {value:>10.1f} {target:>10} {alert:>10} {status:>6}")

    print()
    return all_pass


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        kpis = await fetch_kpis(session)

    await engine.dispose()

    passed = print_report(kpis)
    if not passed:
        print("KPI check FAILED — one or more metrics breached alert threshold.")
        sys.exit(1)
    print("KPI check PASSED.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run against the seeded DB**

```powershell
# Ensure postgres is running with seed data (python scripts/seed_db.py)
.venv\Scripts\python tests/evals/kpi_check.py
```

Expected (with seed data): table prints; `KPI check PASSED.` or `FAILED.` depending on data values. Script must not crash or raise an exception.

- [ ] **Step 3: Commit**

```powershell
git add tests/evals/kpi_check.py
git commit -m "feat: add kpi_check.py — PRD Section 11 KPI reporter (TASK-011)"
```

---

## Task 10: Full suite run and final commit

- [ ] **Step 1: Run all mock-based evals together**

```powershell
.venv\Scripts\pytest tests/evals/test_worker_rate_limit.py tests/evals/test_timezone_gate.py tests/evals/test_structured_output.py tests/evals/test_signature_verification.py -v
```

Expected: 13 tests collected, all PASSED.

- [ ] **Step 2: Run the load test**

```powershell
.venv\Scripts\python tests/evals/locustfile.py
```

Expected: `PASS: peak CPS < 1.1`

- [ ] **Step 3: Run real-DB eval (requires postgres)**

```powershell
docker compose up postgres -d
.venv\Scripts\pytest tests/evals/test_dnc_regression.py -v
```

Expected: `test_zero_dnc_leads_dispatched PASSED`

- [ ] **Step 4: Update CLAUDE.md Phase Status**

In `CLAUDE.md`, update the Phase 11 (evals) status line to:

```
**Phase 11 (evals):** COMPLETE — tests/evals/ suite implemented; 13 new pytest tests + locustfile + kpi_check
```

- [ ] **Step 5: Final commit**

```powershell
git add CLAUDE.md
git commit -m "feat: complete TASK-011 evals suite — 13 tests, locustfile, kpi_check"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ test_dnc_regression — 100 leads / 10 DNC / real DB (Task 3)
- ✅ test_worker_rate_limit — 10 leads, mock, elapsed ≥ 9.0s (Task 4)
- ✅ test_timezone_gate — 5 timezones, freezegun (Task 5)
- ✅ test_structured_output — 3 transcripts, schema validate (Task 6)
- ✅ test_signature_verification — valid 200 / tampered 403 / missing 422 (Task 7)
- ✅ locustfile.py — 10 leads, real sleep, peak CPS < 1.1 (Task 8)
- ✅ kpi_check.py — 4 queryable KPIs + 2 N/A flagged (Task 9)

**HTTP status code correction:** Spec said 401 for bad HMAC; actual code in `app/webhook_receiver/dependencies.py` raises **403**. Plan uses 403. Missing header raises FastAPI **422** (required header not supplied).

**`next_retry_at` in DNC test:** Must be set to a past datetime. The worker SQL uses `AND l.next_retry_at <= :now` — NULL values do NOT satisfy this condition in PostgreSQL (NULL comparison yields NULL, not TRUE). All 100 test leads use `next_retry_at = datetime.utcnow() - timedelta(minutes=5)`.

**Locust LEAD_COUNT = 10:** 1000 leads × 1.0s sleep = 1000s is impractical for CI. 10 leads ≈ 10s validates the same invariant. Set `LEAD_COUNT = 1000` for extended manual load tests.
