# Webhook Receiver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone FastAPI service on port 8001 that receives Retell AI webhook events, verifies HMAC-SHA256 signatures, protects against replays via Redis, and writes call lifecycle state to PostgreSQL through a typed service layer.

**Architecture:** Single `POST /webhook` endpoint; `dependencies.py` reads raw body and verifies HMAC; `router.py` handles replay protection and calls `dispatcher.py`; dispatcher routes by `event` field to thin handlers; handlers call services that own all SQL in `async with session.begin()` transactions. RQ stub job enqueued on `call_analyzed`.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2.0 async, redis.asyncio (redis-py ≥ 4.5), Pydantic v2, RQ 1.16, httpx 0.27, pytest-asyncio 0.24

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Modify | Add `redis>=4.5.0` |
| `app/core/settings.py` | Modify | Add `RETELL_WEBHOOK_SECRET`, `REDIS_URL`, `WEBHOOK_PORT` |
| `app/webhook_receiver/__init__.py` | Create | Empty package marker |
| `app/webhook_receiver/config.py` | Create | Module constants: `FAILED_DISCONNECT_REASONS`, TTLs |
| `app/webhook_receiver/signature_verifier.py` | Create | Pure HMAC-SHA256 verification (no FastAPI imports) |
| `app/webhook_receiver/dependencies.py` | Create | FastAPI `Depends`: read raw body, verify HMAC |
| `app/webhook_receiver/dispatcher.py` | Create | Route `event` field → handler; WARNING on unknown |
| `app/webhook_receiver/router.py` | Create | `POST /webhook`: replay check, call dispatcher |
| `app/webhook_receiver/main.py` | Create | FastAPI app, lifespan (DB + Redis init/close) |
| `app/webhook_receiver/schemas/__init__.py` | Create | Re-export all payload types |
| `app/webhook_receiver/schemas/base.py` | Create | `BaseRetellEvent`: `event`, `call_id`, `timestamp` |
| `app/webhook_receiver/schemas/call_started.py` | Create | `CallStartedPayload` |
| `app/webhook_receiver/schemas/call_ended.py` | Create | `CallEndedPayload` |
| `app/webhook_receiver/schemas/call_analyzed.py` | Create | `CallAnalyzedPayload` |
| `app/webhook_receiver/schemas/transcript_updated.py` | Create | `TranscriptUpdatedPayload` |
| `app/webhook_receiver/handlers/__init__.py` | Create | Import all handler modules |
| `app/webhook_receiver/handlers/call_started.py` | Create | Upsert call_log, set lead `calling` |
| `app/webhook_receiver/handlers/call_ended.py` | Create | Finalize call_log, set lead `completed`/`failed` |
| `app/webhook_receiver/handlers/call_analyzed.py` | Create | Write transcript, enqueue RQ stub |
| `app/webhook_receiver/handlers/transcript_updated.py` | Create | Structured log only |
| `app/webhook_receiver/services/__init__.py` | Create | Import all service modules |
| `app/webhook_receiver/services/call_log_service.py` | Create | `upsert_call_log`, `update_call_end` |
| `app/webhook_receiver/services/lead_service.py` | Create | `set_lead_status` |
| `app/webhook_receiver/services/transcript_service.py` | Create | `create_transcript` |
| `app/webhook_receiver/services/queue_service.py` | Create | `enqueue_analysis` via RQ |
| `app/webhook_receiver/README.md` | Create | Developer documentation |
| `tests/unit/test_signature_verifier.py` | Create | 5 pure HMAC tests |
| `tests/unit/test_webhook_schemas.py` | Create | Pydantic validation tests |
| `tests/unit/test_dispatcher.py` | Create | Dispatch routing tests |
| `tests/integration/test_webhook_router.py` | Create | Full endpoint integration tests |

---

### Task 1: Add Redis dependency + extend settings

**Files:**
- Modify: `requirements.txt`
- Modify: `app/core/settings.py`

- [ ] **Step 1: Add redis to requirements.txt**

Open `requirements.txt` and add after the `rq` line:

```
redis>=4.5.0
```

Full file after edit:
```
sqlalchemy==2.0.48
asyncpg==0.30.0
alembic==1.13.0
psycopg2-binary==2.9.9
fastapi==0.115.0
uvicorn==0.30.0
pytest==8.2.0
pytest-asyncio==0.24.0
pydantic==2.6.0
pydantic-settings==2.1.0
pytz==2024.1
httpx==0.27.0
rq==1.16.1
redis>=4.5.0
```

- [ ] **Step 2: Install the new dependency**

Run: `pip install "redis>=4.5.0"`
Expected: `Successfully installed redis-...`

- [ ] **Step 3: Extend app/core/settings.py with webhook fields**

```python
# app/core/settings.py
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
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
    RETELL_WEBHOOK_SECRET: str = Field(
        default="",
        description="Retell AI webhook signing secret for HMAC-SHA256 verification"
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL for replay protection and RQ queue"
    )
    WEBHOOK_PORT: int = Field(
        default=8001,
        description="Port for the webhook receiver FastAPI app"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
```

- [ ] **Step 4: Verify settings load**

Run: `python -m pytest --collect-only -q 2>&1 | head -5`
Expected: no import errors

- [ ] **Step 5: Commit**

```bash
git add requirements.txt app/core/settings.py
git commit -m "feat: add redis dependency and webhook settings fields"
```

---

### Task 2: Module scaffolding + config constants

**Files:**
- Create: `app/webhook_receiver/__init__.py`
- Create: `app/webhook_receiver/config.py`
- Create: `app/webhook_receiver/schemas/__init__.py` (empty)
- Create: `app/webhook_receiver/handlers/__init__.py` (empty)
- Create: `app/webhook_receiver/services/__init__.py` (empty)

- [ ] **Step 1: Create package directories**

Run:
```powershell
New-Item -ItemType Directory -Path app/webhook_receiver/schemas -Force
New-Item -ItemType Directory -Path app/webhook_receiver/handlers -Force
New-Item -ItemType Directory -Path app/webhook_receiver/services -Force
```

- [ ] **Step 2: Create app/webhook_receiver/__init__.py**

```python
# app/webhook_receiver/__init__.py
```

- [ ] **Step 3: Create app/webhook_receiver/config.py**

```python
# app/webhook_receiver/config.py

FAILED_DISCONNECT_REASONS: frozenset[str] = frozenset({
    "error",
    "timeout",
    "dial_timeout",
    "dial_failed",
})

REPLAY_TTL_SECONDS: int = 600       # 10 minutes
TIMESTAMP_TOLERANCE_SECONDS: int = 300  # 5 minutes
```

- [ ] **Step 4: Create empty __init__.py files**

```python
# app/webhook_receiver/schemas/__init__.py
```

```python
# app/webhook_receiver/handlers/__init__.py
```

```python
# app/webhook_receiver/services/__init__.py
```

- [ ] **Step 5: Verify import**

Run: `python -c "from app.webhook_receiver.config import FAILED_DISCONNECT_REASONS; print(FAILED_DISCONNECT_REASONS)"`
Expected: `frozenset({'error', 'timeout', 'dial_timeout', 'dial_failed'})`

- [ ] **Step 6: Commit**

```bash
git add app/webhook_receiver/
git commit -m "feat: scaffold webhook_receiver module structure"
```

---

### Task 3: Signature verifier (pure, TDD)

**Files:**
- Create: `tests/unit/test_signature_verifier.py`
- Create: `app/webhook_receiver/signature_verifier.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_signature_verifier.py
import hmac
import hashlib
import pytest
from app.webhook_receiver.signature_verifier import verify_retell_signature


def _make_sig(body: bytes, secret: str) -> str:
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()


def test_valid_signature_passes():
    body = b'{"event":"call_started","call_id":"abc"}'
    secret = "test-secret"
    assert verify_retell_signature(body, _make_sig(body, secret), secret) is True


def test_tampered_body_fails():
    body = b'{"event":"call_started","call_id":"abc"}'
    tampered = b'{"event":"call_started","call_id":"hacked"}'
    secret = "test-secret"
    sig = _make_sig(body, secret)
    assert verify_retell_signature(tampered, sig, secret) is False


def test_wrong_secret_fails():
    body = b'{"event":"call_started","call_id":"abc"}'
    sig = _make_sig(body, "correct")
    assert verify_retell_signature(body, sig, "wrong") is False


def test_empty_body_valid_sig():
    body = b""
    secret = "s"
    assert verify_retell_signature(body, _make_sig(body, secret), secret) is True


def test_returns_bool_not_string():
    body = b'{"test":true}'
    secret = "secret"
    result = verify_retell_signature(body, _make_sig(body, secret), secret)
    assert isinstance(result, bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_signature_verifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.webhook_receiver.signature_verifier'`

- [ ] **Step 3: Implement signature_verifier.py**

```python
# app/webhook_receiver/signature_verifier.py
import hmac
import hashlib


def verify_retell_signature(
    raw_body: bytes,
    signature_header: str,
    webhook_secret: str,
) -> bool:
    expected = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_signature_verifier.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_signature_verifier.py app/webhook_receiver/signature_verifier.py
git commit -m "feat: add HMAC-SHA256 webhook signature verifier"
```

---

### Task 4: Pydantic schemas (TDD)

**Files:**
- Create: `tests/unit/test_webhook_schemas.py`
- Create: `app/webhook_receiver/schemas/base.py`
- Create: `app/webhook_receiver/schemas/call_started.py`
- Create: `app/webhook_receiver/schemas/call_ended.py`
- Create: `app/webhook_receiver/schemas/call_analyzed.py`
- Create: `app/webhook_receiver/schemas/transcript_updated.py`
- Modify: `app/webhook_receiver/schemas/__init__.py`

- [ ] **Step 1: Write failing schema tests**

```python
# tests/unit/test_webhook_schemas.py
import pytest
from pydantic import ValidationError
from app.webhook_receiver.schemas import (
    BaseRetellEvent,
    CallStartedPayload,
    CallEndedPayload,
    CallAnalyzedPayload,
    TranscriptUpdatedPayload,
)


class TestBaseRetellEvent:
    def test_parses_required_fields(self):
        e = BaseRetellEvent(event="call_started", call_id="abc123")
        assert e.event == "call_started"
        assert e.call_id == "abc123"

    def test_missing_event_raises(self):
        with pytest.raises(ValidationError):
            BaseRetellEvent(call_id="abc")

    def test_missing_call_id_raises(self):
        with pytest.raises(ValidationError):
            BaseRetellEvent(event="call_started")

    def test_extra_fields_allowed(self):
        e = BaseRetellEvent(event="call_started", call_id="abc", unknown_field="ignored")
        assert e.call_id == "abc"

    def test_timestamp_optional(self):
        e = BaseRetellEvent(event="call_started", call_id="abc")
        assert e.timestamp is None


class TestCallStartedPayload:
    def test_parses_full_payload(self):
        p = CallStartedPayload(
            event="call_started",
            call_id="call_001",
            from_number="+11234567890",
            to_number="+10987654321",
            agent_id="agent_abc",
            start_timestamp=1746700000000,
            metadata={"lead_id": "uuid-here"},
        )
        assert p.call_id == "call_001"
        assert p.metadata == {"lead_id": "uuid-here"}

    def test_all_fields_optional_except_base(self):
        p = CallStartedPayload(event="call_started", call_id="c1")
        assert p.from_number is None
        assert p.metadata is None


class TestCallEndedPayload:
    def test_parses_full_payload(self):
        p = CallEndedPayload(
            event="call_ended",
            call_id="call_001",
            end_timestamp=1746700060000,
            duration_ms=60000,
            disconnect_reason="user_hangup",
            recording_url="https://cdn.retell.ai/rec.mp3",
        )
        assert p.duration_ms == 60000
        assert p.disconnect_reason == "user_hangup"

    def test_all_fields_optional(self):
        p = CallEndedPayload(event="call_ended", call_id="c1")
        assert p.duration_ms is None
        assert p.disconnect_reason is None


class TestCallAnalyzedPayload:
    def test_parses_transcript(self):
        p = CallAnalyzedPayload(
            event="call_analyzed",
            call_id="c1",
            transcript="Agent: Hi\nUser: Hello",
        )
        assert "Agent" in p.transcript

    def test_transcript_optional(self):
        p = CallAnalyzedPayload(event="call_analyzed", call_id="c1")
        assert p.transcript is None


class TestTranscriptUpdatedPayload:
    def test_parses_basic(self):
        p = TranscriptUpdatedPayload(
            event="transcript_updated",
            call_id="c1",
            transcript="partial...",
        )
        assert p.call_id == "c1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_webhook_schemas.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement all schema files**

```python
# app/webhook_receiver/schemas/base.py
from pydantic import BaseModel, ConfigDict


class BaseRetellEvent(BaseModel):
    event: str
    call_id: str
    timestamp: int | None = None

    model_config = ConfigDict(extra="allow")
```

```python
# app/webhook_receiver/schemas/call_started.py
from .base import BaseRetellEvent


class CallStartedPayload(BaseRetellEvent):
    from_number: str | None = None
    to_number: str | None = None
    agent_id: str | None = None
    metadata: dict | None = None
    start_timestamp: int | None = None  # milliseconds since epoch
```

```python
# app/webhook_receiver/schemas/call_ended.py
from .base import BaseRetellEvent


class CallEndedPayload(BaseRetellEvent):
    end_timestamp: int | None = None  # milliseconds since epoch
    duration_ms: int | None = None
    disconnect_reason: str | None = None
    recording_url: str | None = None
```

```python
# app/webhook_receiver/schemas/call_analyzed.py
from .base import BaseRetellEvent


class CallAnalyzedPayload(BaseRetellEvent):
    transcript: str | None = None
```

```python
# app/webhook_receiver/schemas/transcript_updated.py
from .base import BaseRetellEvent


class TranscriptUpdatedPayload(BaseRetellEvent):
    transcript: str | None = None
```

```python
# app/webhook_receiver/schemas/__init__.py
from .base import BaseRetellEvent
from .call_started import CallStartedPayload
from .call_ended import CallEndedPayload
from .call_analyzed import CallAnalyzedPayload
from .transcript_updated import TranscriptUpdatedPayload

__all__ = [
    "BaseRetellEvent",
    "CallStartedPayload",
    "CallEndedPayload",
    "CallAnalyzedPayload",
    "TranscriptUpdatedPayload",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_webhook_schemas.py -v`
Expected: 13 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_webhook_schemas.py app/webhook_receiver/schemas/
git commit -m "feat: add Pydantic schemas for Retell webhook events"
```

---

### Task 5: Service layer (TDD)

**Files:**
- Create: `tests/unit/test_webhook_services.py`
- Create: `app/webhook_receiver/services/call_log_service.py`
- Create: `app/webhook_receiver/services/lead_service.py`
- Create: `app/webhook_receiver/services/transcript_service.py`
- Create: `app/webhook_receiver/services/queue_service.py`
- Modify: `app/webhook_receiver/services/__init__.py`

- [ ] **Step 1: Write failing service tests**

```python
# tests/unit/test_webhook_services.py
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.webhook_receiver.services.call_log_service import upsert_call_log, update_call_end
from app.webhook_receiver.services.lead_service import set_lead_status
from app.webhook_receiver.services.transcript_service import create_transcript
from app.webhook_receiver.services.queue_service import enqueue_analysis
from app.models.call import Call, CallStatus
from app.models.contact import Contact, ContactStatus
from app.models.transcript import Transcript


def _make_mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()
    return session


class TestUpsertCallLog:
    @pytest.mark.asyncio
    async def test_updates_existing_call_log(self):
        existing = MagicMock(spec=Call)
        existing.start_time = None

        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute.return_value = result_mock

        now = datetime.now(tz=timezone.utc)
        result = await upsert_call_log(session, "retell_001", now)

        assert result is existing
        assert existing.start_time == now
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_call_log_when_not_found(self):
        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        lead_id = uuid.uuid4()
        now = datetime.now(tz=timezone.utc)
        result = await upsert_call_log(session, "retell_002", now, lead_id=lead_id)

        session.add.assert_called_once()
        added_call = session.add.call_args[0][0]
        assert added_call.retell_call_id == "retell_002"
        assert added_call.lead_id == lead_id

    @pytest.mark.asyncio
    async def test_raises_if_no_lead_id_and_not_found(self):
        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        with pytest.raises(ValueError, match="lead_id"):
            await upsert_call_log(session, "retell_003", datetime.now(tz=timezone.utc))


class TestUpdateCallEnd:
    @pytest.mark.asyncio
    async def test_updates_found_call(self):
        existing = MagicMock(spec=Call)
        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute.return_value = result_mock

        now = datetime.now(tz=timezone.utc)
        result = await update_call_end(session, "retell_001", now, 60, "user_hangup", "https://rec.mp3")

        assert result is existing
        assert existing.end_time == now
        assert existing.duration_sec == 60
        assert existing.disconnect_reason == "user_hangup"
        assert existing.recording_url == "https://rec.mp3"

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self):
        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        result = await update_call_end(session, "missing", datetime.now(tz=timezone.utc), None, None, None)
        assert result is None


class TestSetLeadStatus:
    @pytest.mark.asyncio
    async def test_executes_update(self):
        session = _make_mock_session()
        lead_id = uuid.uuid4()
        await set_lead_status(session, lead_id, ContactStatus.COMPLETED)
        session.execute.assert_called_once()


class TestCreateTranscript:
    @pytest.mark.asyncio
    async def test_adds_transcript_to_session(self):
        session = _make_mock_session()
        call_id = uuid.uuid4()
        result = await create_transcript(session, call_id, "Agent: Hi\nUser: Hello")
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.call_id == call_id
        assert added.raw_transcript == "Agent: Hi\nUser: Hello"


class TestEnqueueAnalysis:
    @pytest.mark.asyncio
    async def test_enqueues_without_error(self):
        call_id = str(uuid.uuid4())
        with patch("app.webhook_receiver.services.queue_service._enqueue_sync") as mock_enqueue:
            await enqueue_analysis("redis://localhost:6379", call_id)
        mock_enqueue.assert_called_once_with("redis://localhost:6379", call_id)

    @pytest.mark.asyncio
    async def test_logs_error_on_redis_failure(self):
        call_id = str(uuid.uuid4())
        with patch(
            "app.webhook_receiver.services.queue_service._enqueue_sync",
            side_effect=Exception("Redis down"),
        ):
            # Should not raise — error is logged, not re-raised
            await enqueue_analysis("redis://localhost:6379", call_id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_webhook_services.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement call_log_service.py**

```python
# app/webhook_receiver/services/call_log_service.py
import logging
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call, CallStatus

logger = logging.getLogger(__name__)


async def upsert_call_log(
    session: AsyncSession,
    retell_call_id: str,
    start_time: datetime,
    lead_id: UUID | None = None,
) -> Call:
    result = await session.execute(
        sa.select(Call).where(Call.retell_call_id == retell_call_id)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.start_time = start_time
        await session.flush()
        logger.info("Updated call_log start_time", extra={"retell_call_id": retell_call_id})
        return existing

    if lead_id is None:
        raise ValueError(f"Cannot create call_log without lead_id for retell_call_id={retell_call_id}")

    call = Call(
        retell_call_id=retell_call_id,
        lead_id=lead_id,
        start_time=start_time,
        status=CallStatus.CALLING,
    )
    session.add(call)
    await session.flush()
    logger.info("Created call_log", extra={"retell_call_id": retell_call_id})
    return call


async def update_call_end(
    session: AsyncSession,
    retell_call_id: str,
    end_time: datetime,
    duration_sec: int | None,
    disconnect_reason: str | None,
    recording_url: str | None,
) -> Call | None:
    result = await session.execute(
        sa.select(Call).where(Call.retell_call_id == retell_call_id)
    )
    call = result.scalar_one_or_none()

    if call is None:
        logger.warning("call_log not found", extra={"retell_call_id": retell_call_id})
        return None

    call.end_time = end_time
    call.duration_sec = duration_sec
    call.disconnect_reason = disconnect_reason
    call.recording_url = recording_url
    await session.flush()
    return call
```

- [ ] **Step 4: Implement lead_service.py**

```python
# app/webhook_receiver/services/lead_service.py
import logging
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact, ContactStatus

logger = logging.getLogger(__name__)


async def set_lead_status(
    session: AsyncSession,
    lead_id: UUID,
    status: ContactStatus,
) -> None:
    await session.execute(
        sa.update(Contact)
        .where(Contact.id == lead_id)
        .values(status=status)
    )
    logger.info(
        "Updated lead status",
        extra={"lead_id": str(lead_id), "status": status.value},
    )
```

- [ ] **Step 5: Implement transcript_service.py**

```python
# app/webhook_receiver/services/transcript_service.py
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transcript import Transcript

logger = logging.getLogger(__name__)


async def create_transcript(
    session: AsyncSession,
    call_id: UUID,
    raw_transcript: str | None,
) -> Transcript:
    transcript = Transcript(
        call_id=call_id,
        raw_transcript=raw_transcript,
    )
    session.add(transcript)
    await session.flush()
    logger.info("Created call_transcript", extra={"call_id": str(call_id)})
    return transcript
```

- [ ] **Step 6: Implement queue_service.py**

```python
# app/webhook_receiver/services/queue_service.py
import asyncio
import logging

import redis as sync_redis
from rq import Queue

logger = logging.getLogger(__name__)

POST_CALL_ANALYSIS_JOB = "app.post_call_analysis.worker.analyze_call"


def _enqueue_sync(redis_url: str, call_id: str) -> None:
    conn = sync_redis.from_url(redis_url)
    q = Queue(connection=conn)
    q.enqueue(POST_CALL_ANALYSIS_JOB, call_id=call_id)


async def enqueue_analysis(redis_url: str, call_id: str) -> None:
    try:
        await asyncio.to_thread(_enqueue_sync, redis_url, call_id)
        logger.info("Enqueued post_call_analysis job", extra={"call_id": call_id})
    except Exception as exc:
        logger.error(
            "Failed to enqueue post_call_analysis job",
            extra={"call_id": call_id, "error": str(exc)},
        )
```

- [ ] **Step 7: Update services/__init__.py**

```python
# app/webhook_receiver/services/__init__.py
from . import call_log_service, lead_service, transcript_service, queue_service

__all__ = ["call_log_service", "lead_service", "transcript_service", "queue_service"]
```

- [ ] **Step 8: Run all service tests**

Run: `python -m pytest tests/unit/test_webhook_services.py -v`
Expected: 9 PASSED

- [ ] **Step 9: Commit**

```bash
git add tests/unit/test_webhook_services.py app/webhook_receiver/services/
git commit -m "feat: add webhook receiver service layer"
```

---

### Task 6: Event handlers

**Files:**
- Create: `app/webhook_receiver/handlers/call_started.py`
- Create: `app/webhook_receiver/handlers/call_ended.py`
- Create: `app/webhook_receiver/handlers/call_analyzed.py`
- Create: `app/webhook_receiver/handlers/transcript_updated.py`
- Modify: `app/webhook_receiver/handlers/__init__.py`

Handlers are thin orchestrators — they parse the payload, open a DB session, and delegate to services. No SQL in handlers.

- [ ] **Step 1: Implement handlers/call_started.py**

```python
# app/webhook_receiver/handlers/call_started.py
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.contact import ContactStatus
from app.webhook_receiver.schemas.call_started import CallStartedPayload
from app.webhook_receiver.services import call_log_service, lead_service

logger = logging.getLogger(__name__)


async def handle_call_started(
    payload: CallStartedPayload,
    session_factory: async_sessionmaker,
) -> None:
    retell_call_id = payload.call_id

    start_time = datetime.now(tz=timezone.utc)
    if payload.start_timestamp is not None:
        start_time = datetime.fromtimestamp(payload.start_timestamp / 1000, tz=timezone.utc)

    lead_id: uuid.UUID | None = None
    if payload.metadata:
        raw_id = payload.metadata.get("lead_id")
        if raw_id:
            try:
                lead_id = uuid.UUID(raw_id)
            except ValueError:
                logger.warning("Invalid lead_id in metadata", extra={"raw_lead_id": raw_id})

    async with session_factory() as session:
        async with session.begin():
            call = await call_log_service.upsert_call_log(
                session=session,
                retell_call_id=retell_call_id,
                start_time=start_time,
                lead_id=lead_id,
            )
            if call.lead_id:
                await lead_service.set_lead_status(
                    session=session,
                    lead_id=call.lead_id,
                    status=ContactStatus.CALLING,
                )

    logger.info("Handled call_started", extra={"retell_call_id": retell_call_id})
```

- [ ] **Step 2: Implement handlers/call_ended.py**

```python
# app/webhook_receiver/handlers/call_ended.py
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.contact import ContactStatus
from app.webhook_receiver.config import FAILED_DISCONNECT_REASONS
from app.webhook_receiver.schemas.call_ended import CallEndedPayload
from app.webhook_receiver.services import call_log_service, lead_service

logger = logging.getLogger(__name__)


async def handle_call_ended(
    payload: CallEndedPayload,
    session_factory: async_sessionmaker,
) -> None:
    retell_call_id = payload.call_id

    end_time = datetime.now(tz=timezone.utc)
    if payload.end_timestamp is not None:
        end_time = datetime.fromtimestamp(payload.end_timestamp / 1000, tz=timezone.utc)

    duration_sec: int | None = None
    if payload.duration_ms is not None:
        duration_sec = payload.duration_ms // 1000

    lead_status = (
        ContactStatus.FAILED
        if payload.disconnect_reason in FAILED_DISCONNECT_REASONS
        else ContactStatus.COMPLETED
    )

    async with session_factory() as session:
        async with session.begin():
            call = await call_log_service.update_call_end(
                session=session,
                retell_call_id=retell_call_id,
                end_time=end_time,
                duration_sec=duration_sec,
                disconnect_reason=payload.disconnect_reason,
                recording_url=payload.recording_url,
            )
            if call is not None and call.lead_id is not None:
                await lead_service.set_lead_status(
                    session=session,
                    lead_id=call.lead_id,
                    status=lead_status,
                )

    logger.info(
        "Handled call_ended",
        extra={"retell_call_id": retell_call_id, "disconnect_reason": payload.disconnect_reason},
    )
```

- [ ] **Step 3: Implement handlers/call_analyzed.py**

```python
# app/webhook_receiver/handlers/call_analyzed.py
import logging

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.settings import settings
from app.models.call import Call
from app.webhook_receiver.schemas.call_analyzed import CallAnalyzedPayload
from app.webhook_receiver.services import transcript_service, queue_service

logger = logging.getLogger(__name__)


async def handle_call_analyzed(
    payload: CallAnalyzedPayload,
    session_factory: async_sessionmaker,
) -> None:
    retell_call_id = payload.call_id
    transcript_call_id: str | None = None

    async with session_factory() as session:
        async with session.begin():
            result = await session.execute(
                sa.select(Call).where(Call.retell_call_id == retell_call_id)
            )
            call = result.scalar_one_or_none()

            if call is None:
                logger.warning(
                    "call_log not found for call_analyzed",
                    extra={"retell_call_id": retell_call_id},
                )
                return

            transcript = await transcript_service.create_transcript(
                session=session,
                call_id=call.id,
                raw_transcript=payload.transcript,
            )
            transcript_call_id = str(transcript.call_id)

    if transcript_call_id:
        await queue_service.enqueue_analysis(
            redis_url=settings.REDIS_URL,
            call_id=transcript_call_id,
        )

    logger.info("Handled call_analyzed", extra={"retell_call_id": retell_call_id})
```

- [ ] **Step 4: Implement handlers/transcript_updated.py**

```python
# app/webhook_receiver/handlers/transcript_updated.py
import logging

from app.webhook_receiver.schemas.transcript_updated import TranscriptUpdatedPayload

logger = logging.getLogger(__name__)


async def handle_transcript_updated(payload: TranscriptUpdatedPayload) -> None:
    logger.info(
        "Received transcript_updated (no DB write — dashboard not yet built)",
        extra={"retell_call_id": payload.call_id},
    )
```

- [ ] **Step 5: Update handlers/__init__.py**

```python
# app/webhook_receiver/handlers/__init__.py
from . import call_started, call_ended, call_analyzed, transcript_updated

__all__ = ["call_started", "call_ended", "call_analyzed", "transcript_updated"]
```

- [ ] **Step 6: Smoke test imports**

Run: `python -c "from app.webhook_receiver.handlers import call_started, call_ended, call_analyzed, transcript_updated; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add app/webhook_receiver/handlers/
git commit -m "feat: add webhook event handlers (call_started, call_ended, call_analyzed, transcript_updated)"
```

---

### Task 7: Dispatcher (TDD)

**Files:**
- Create: `tests/unit/test_dispatcher.py`
- Create: `app/webhook_receiver/dispatcher.py`

- [ ] **Step 1: Write failing dispatcher tests**

```python
# tests/unit/test_dispatcher.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.webhook_receiver.dispatcher import dispatch
from app.webhook_receiver.schemas.base import BaseRetellEvent


def _base_event(event_type: str, call_id: str = "c1") -> BaseRetellEvent:
    return BaseRetellEvent(event=event_type, call_id=call_id)


def _raw(event_type: str, call_id: str = "c1") -> dict:
    return {"event": event_type, "call_id": call_id}


@pytest.mark.asyncio
async def test_call_started_dispatches_to_handler():
    factory = MagicMock()
    with patch("app.webhook_receiver.handlers.call_started.handle_call_started", AsyncMock()) as mock_h:
        await dispatch(_base_event("call_started"), _raw("call_started"), factory)
    mock_h.assert_called_once()


@pytest.mark.asyncio
async def test_call_ended_dispatches_to_handler():
    factory = MagicMock()
    with patch("app.webhook_receiver.handlers.call_ended.handle_call_ended", AsyncMock()) as mock_h:
        await dispatch(_base_event("call_ended"), _raw("call_ended"), factory)
    mock_h.assert_called_once()


@pytest.mark.asyncio
async def test_call_analyzed_dispatches_to_handler():
    factory = MagicMock()
    with patch("app.webhook_receiver.handlers.call_analyzed.handle_call_analyzed", AsyncMock()) as mock_h:
        await dispatch(_base_event("call_analyzed"), _raw("call_analyzed"), factory)
    mock_h.assert_called_once()


@pytest.mark.asyncio
async def test_transcript_updated_dispatches_to_handler():
    factory = MagicMock()
    with patch("app.webhook_receiver.handlers.transcript_updated.handle_transcript_updated", AsyncMock()) as mock_h:
        await dispatch(_base_event("transcript_updated"), _raw("transcript_updated"), factory)
    mock_h.assert_called_once()


@pytest.mark.asyncio
async def test_unknown_event_type_does_not_raise():
    factory = MagicMock()
    # Should complete without exception
    await dispatch(_base_event("call_something_future"), _raw("call_something_future"), factory)


@pytest.mark.asyncio
async def test_unknown_event_type_logs_warning(caplog):
    import logging
    factory = MagicMock()
    with caplog.at_level(logging.WARNING, logger="app.webhook_receiver.dispatcher"):
        await dispatch(_base_event("unknown_event_xyz"), _raw("unknown_event_xyz"), factory)
    assert any("unknown_event_xyz" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_dispatcher.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement dispatcher.py**

```python
# app/webhook_receiver/dispatcher.py
import logging
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.webhook_receiver.schemas import (
    BaseRetellEvent,
    CallStartedPayload,
    CallEndedPayload,
    CallAnalyzedPayload,
    TranscriptUpdatedPayload,
)
from app.webhook_receiver.handlers import call_started, call_ended, call_analyzed, transcript_updated

logger = logging.getLogger(__name__)


async def dispatch(
    base_event: BaseRetellEvent,
    raw_dict: dict,
    session_factory: async_sessionmaker,
) -> None:
    event_type = base_event.event

    if event_type == "call_started":
        await call_started.handle_call_started(
            payload=CallStartedPayload(**raw_dict),
            session_factory=session_factory,
        )
    elif event_type == "call_ended":
        await call_ended.handle_call_ended(
            payload=CallEndedPayload(**raw_dict),
            session_factory=session_factory,
        )
    elif event_type == "call_analyzed":
        await call_analyzed.handle_call_analyzed(
            payload=CallAnalyzedPayload(**raw_dict),
            session_factory=session_factory,
        )
    elif event_type == "transcript_updated":
        await transcript_updated.handle_transcript_updated(
            payload=TranscriptUpdatedPayload(**raw_dict),
        )
    else:
        logger.warning(
            "Unknown webhook event type — ignoring",
            extra={"event_type": event_type, "call_id": base_event.call_id},
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_dispatcher.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_dispatcher.py app/webhook_receiver/dispatcher.py
git commit -m "feat: add webhook event dispatcher"
```

---

### Task 8: FastAPI dependencies

**Files:**
- Create: `app/webhook_receiver/dependencies.py`

- [ ] **Step 1: Implement dependencies.py**

```python
# app/webhook_receiver/dependencies.py
import logging

from fastapi import Header, HTTPException, Request

from app.core.settings import settings
from app.webhook_receiver.signature_verifier import verify_retell_signature

logger = logging.getLogger(__name__)


async def verified_webhook_body(
    request: Request,
    x_retell_signature: str = Header(...),
) -> bytes:
    raw_body = await request.body()

    if not verify_retell_signature(raw_body, x_retell_signature, settings.RETELL_WEBHOOK_SECRET):
        logger.warning(
            "Webhook signature verification failed",
            extra={"remote": request.client.host if request.client else "unknown"},
        )
        raise HTTPException(status_code=403, detail="Invalid signature")

    return raw_body
```

- [ ] **Step 2: Smoke test import**

Run: `python -c "from app.webhook_receiver.dependencies import verified_webhook_body; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/webhook_receiver/dependencies.py
git commit -m "feat: add HMAC verification FastAPI dependency"
```

---

### Task 9: Router + FastAPI app

**Files:**
- Create: `app/webhook_receiver/router.py`
- Create: `app/webhook_receiver/main.py`

- [ ] **Step 1: Implement router.py**

```python
# app/webhook_receiver/router.py
import json
import logging
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.webhook_receiver.config import REPLAY_TTL_SECONDS
from app.webhook_receiver.dependencies import verified_webhook_body
from app.webhook_receiver.dispatcher import dispatch
from app.webhook_receiver.schemas import BaseRetellEvent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook")
async def webhook_endpoint(
    request: Request,
    raw_body: bytes = Depends(verified_webhook_body),
) -> JSONResponse:
    start_ts = time.monotonic()

    payload_dict = json.loads(raw_body)
    base_event = BaseRetellEvent(**payload_dict)
    event_type = base_event.event
    call_id = base_event.call_id

    # Redis replay protection
    redis = request.app.state.redis
    replay_key = f"webhook:seen:{call_id}:{event_type}"
    try:
        if await redis.exists(replay_key):
            logger.info(
                "Duplicate webhook event — skipping",
                extra={"event_type": event_type, "call_id": call_id},
            )
            return JSONResponse({"status": "ok"})
        await redis.setex(replay_key, REPLAY_TTL_SECONDS, "1")
    except Exception as exc:
        logger.warning("Redis unavailable for replay check", extra={"error": str(exc)})

    session_factory = request.app.state.session_factory
    await dispatch(base_event, payload_dict, session_factory)

    latency_ms = int((time.monotonic() - start_ts) * 1000)
    logger.info(
        "Webhook processed",
        extra={"event_type": event_type, "call_id": call_id, "processing_latency_ms": latency_ms},
    )

    return JSONResponse({"status": "ok"})
```

- [ ] **Step 2: Implement main.py**

```python
# app/webhook_receiver/main.py
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from app.core.settings import settings
from app.db.session import close_db, init_session_factory
from app.webhook_receiver.router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_factory = await init_session_factory()
    app.state.session_factory = session_factory
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    yield
    await close_db()
    await app.state.redis.aclose()


app = FastAPI(title="Retell Webhook Receiver", lifespan=lifespan)
app.include_router(router)
```

- [ ] **Step 3: Smoke test app import**

Run: `python -c "from app.webhook_receiver.main import app; print(app.title)"`
Expected: `Retell Webhook Receiver`

- [ ] **Step 4: Commit**

```bash
git add app/webhook_receiver/router.py app/webhook_receiver/main.py
git commit -m "feat: add webhook router and FastAPI app with lifespan"
```

---

### Task 10: Integration tests

**Files:**
- Create: `tests/integration/test_webhook_router.py`

- [ ] **Step 1: Write integration tests**

```python
# tests/integration/test_webhook_router.py
import hmac
import hashlib
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from app.webhook_receiver.main import app
from app.webhook_receiver.dependencies import verified_webhook_body

TEST_SECRET = "integration-test-secret"


def _make_sig(body: bytes, secret: str = TEST_SECRET) -> str:
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()


def _payload(event: str, call_id: str = "call_test_001") -> bytes:
    return json.dumps({"event": event, "call_id": call_id}).encode()


@pytest_asyncio.fixture
async def mock_redis():
    r = AsyncMock()
    r.exists = AsyncMock(return_value=0)
    r.setex = AsyncMock()
    r.aclose = AsyncMock()
    return r


@pytest_asyncio.fixture
async def mock_session_factory():
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=cm)
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    session.flush = AsyncMock()
    session.add = MagicMock()

    factory = MagicMock(return_value=cm)
    return factory


@pytest_asyncio.fixture
async def client(mock_redis, mock_session_factory):
    with patch("app.webhook_receiver.main.init_session_factory", AsyncMock(return_value=mock_session_factory)):
        with patch("app.webhook_receiver.main.aioredis.from_url", return_value=mock_redis):
            with patch("app.core.settings.settings.RETELL_WEBHOOK_SECRET", TEST_SECRET):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as c:
                    yield c


@pytest.mark.asyncio
async def test_valid_call_started_returns_200(client):
    body = _payload("call_started")
    # Mock dispatch so real handlers/services don't run (covered by unit tests)
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()):
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_invalid_signature_returns_403(client):
    body = _payload("call_started")
    response = await client.post(
        "/webhook",
        content=body,
        headers={"x-retell-signature": "bad-signature", "content-type": "application/json"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_missing_signature_header_returns_422(client):
    body = _payload("call_started")
    response = await client.post(
        "/webhook",
        content=body,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_event_returns_200_without_dispatch(client, mock_redis):
    mock_redis.exists = AsyncMock(return_value=1)  # Already seen
    body = _payload("call_started", "call_dup_001")

    with patch("app.webhook_receiver.router.dispatch", AsyncMock()) as mock_dispatch:
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
        mock_dispatch.assert_not_called()

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_unknown_event_type_returns_200(client):
    body = _payload("call_new_retell_event_2027")
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()):
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_call_ended_event_routes_to_dispatch(client):
    body = json.dumps({
        "event": "call_ended",
        "call_id": "call_test_002",
        "duration_ms": 45000,
        "disconnect_reason": "user_hangup",
    }).encode()
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()) as mock_dispatch:
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    assert response.status_code == 200
    call_args = mock_dispatch.call_args[0]
    assert call_args[0].event == "call_ended"


@pytest.mark.asyncio
async def test_call_analyzed_event_routes_to_dispatch(client):
    body = json.dumps({
        "event": "call_analyzed",
        "call_id": "call_test_003",
        "transcript": "Agent: Hello\nUser: Hi",
    }).encode()
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()) as mock_dispatch:
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    assert response.status_code == 200
    assert mock_dispatch.call_args[0][0].event == "call_analyzed"


@pytest.mark.asyncio
async def test_transcript_updated_returns_200(client):
    body = _payload("transcript_updated")
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()):
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_replay_key_set_on_new_event(client, mock_redis):
    body = _payload("call_started", "call_new_001")
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()):
        await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    mock_redis.setex.assert_called_once_with(
        "webhook:seen:call_new_001:call_started", 600, "1"
    )
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/integration/test_webhook_router.py -v`
Expected: 9 PASSED

- [ ] **Step 3: Run full test suite to check for regressions**

Run: `python -m pytest tests/unit/test_signature_verifier.py tests/unit/test_webhook_schemas.py tests/unit/test_webhook_services.py tests/unit/test_dispatcher.py tests/integration/test_webhook_router.py -v`
Expected: all PASSED

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_webhook_router.py
git commit -m "test: add webhook router integration tests"
```

---

### Task 11: README + final verification

**Files:**
- Create: `app/webhook_receiver/README.md`

- [ ] **Step 1: Write README**

```markdown
# Webhook Receiver

Standalone FastAPI service (port 8001) that receives Retell AI webhook events, verifies HMAC-SHA256 signatures, and updates call lifecycle state in PostgreSQL.

## Running

```bash
uvicorn app.webhook_receiver.main:app --port 8001 --reload
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `RETELL_WEBHOOK_SECRET` | Yes | — | Retell webhook signing secret |
| `DATABASE_URL` | Yes | — | PostgreSQL async URL |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis for replay protection |
| `WEBHOOK_PORT` | No | `8001` | App port |

## Endpoint

`POST /webhook` — receives all Retell AI event types.

**Request headers:**
- `x-retell-signature`: HMAC-SHA256 hex digest of raw body, keyed with `RETELL_WEBHOOK_SECRET`
- `content-type: application/json`

**Response:** always `{"status": "ok"}` with HTTP 200 if processing succeeded.

**Errors:**
- `403`: Invalid HMAC signature
- `422`: Malformed JSON (missing required fields)
- `500`: Internal error — Retell will retry

## Event Handling

| Event | Action |
|---|---|
| `call_started` | Upsert `call_logs` row (create or set `start_time`); set `leads.status = 'calling'` |
| `call_ended` | Update `call_logs` with `end_time`, `duration_sec`, `disconnect_reason`, `recording_url`; set `leads.status = 'completed'` or `'failed'` |
| `call_analyzed` | Insert `call_transcripts.raw_transcript`; enqueue `app.post_call_analysis.worker.analyze_call` RQ job |
| `transcript_updated` | Structured log only (no DB write until dashboard Module 8) |
| unknown | Log WARNING, return 200 |

## Disconnect Reason → Lead Status Mapping

`"error"`, `"timeout"`, `"dial_timeout"`, `"dial_failed"` → `failed`

All other reasons → `completed`

## Replay Protection

Redis key: `webhook:seen:{call_id}:{event}` with 600s TTL. Prevents duplicate DB writes from Retell's retry logic. Degrades gracefully if Redis is unavailable (allows processing with WARNING log).

## RQ Job Stub

`call_analyzed` enqueues job `app.post_call_analysis.worker.analyze_call` with `call_id` arg. Module 5 implements the actual worker. If Redis is unavailable for enqueue, logs ERROR but does NOT fail the webhook (transcript row is already persisted).

## call_started Metadata

The dialing worker should pass `metadata={"lead_id": str(lead.id)}` in the Retell `create_call` request. This enables the webhook receiver to create a `call_logs` row in the fallback case where the dialing worker's DB write failed before Retell confirmed the call.

## Testing

```bash
python -m pytest tests/unit/test_signature_verifier.py tests/unit/test_webhook_schemas.py tests/unit/test_webhook_services.py tests/unit/test_dispatcher.py tests/integration/test_webhook_router.py -v
```
```

- [ ] **Step 2: Run complete test suite**

Run: `python -m pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: all webhook receiver tests PASSED; any DB-requiring tests may fail without live PostgreSQL (expected)

- [ ] **Step 3: Verify app starts**

Run: `python -c "from app.webhook_receiver.main import app; print('App imports cleanly:', app.title)"`
Expected: `App imports cleanly: Retell Webhook Receiver`

- [ ] **Step 4: Final commit**

```bash
git add app/webhook_receiver/README.md
git commit -m "docs: add webhook receiver developer documentation"
git commit --allow-empty -m "feat: complete webhook receiver module - HMAC verification, Redis replay protection, 4-event handlers, service layer, RQ stub"
```

---

## Dependency Notes

- `metadata.lead_id` in `call_started` payload requires the dialing worker to pass `metadata={"lead_id": str(lead.id)}` when calling Retell's `create_call`. This is a cross-module dependency — document it but do NOT modify the dialing worker in this session.
- The RQ job path `app.post_call_analysis.worker.analyze_call` must match exactly what Module 5 defines as its entry point.
- Redis must be running for replay protection. The service degrades gracefully with a WARNING log if Redis is unreachable.
