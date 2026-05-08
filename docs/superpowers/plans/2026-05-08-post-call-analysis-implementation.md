# Post-Call Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an RQ worker (`analyze_call`) that loads a call transcript, calls Claude Sonnet for structured extraction, runs a DNC keyword safety scan, writes results to PostgreSQL, and handles retries with a dead-letter flag on exhaustion.

**Architecture:** Single orchestration worker (`worker.py`) with separated concerns: `prompts.py` owns the Claude system prompt, `schemas.py` owns the Pydantic output model, `dnc_keywords.py` owns the keyword safety scan. The RQ job is synchronous and uses `asyncio.run()` to call async DB operations. Retry config (3×, backoff 60/120/300s) is passed at enqueue time via an update to `queue_service.py`.

**Tech Stack:** Python 3.13, Anthropic SDK (`anthropic`), SQLAlchemy 2.0 async, RQ 1.16, Pydantic v2, pytest-asyncio

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Modify | Add `anthropic>=0.25.0` |
| `app/core/settings.py` | Modify | Add `ANTHROPIC_API_KEY` field + startup warning |
| `app/post_call_analysis/__init__.py` | Create | Empty package marker |
| `app/post_call_analysis/dnc_keywords.py` | Create | DNC phrase list + `scan(transcript) -> bool` |
| `app/post_call_analysis/schemas.py` | Create | `ExtractionResult` Pydantic model |
| `app/post_call_analysis/prompts.py` | Create | Claude system prompt + `build_user_message()` |
| `app/post_call_analysis/worker.py` | Create | `analyze_call` RQ job, `_run_analysis`, `_write_failure_flag`, `_call_claude` |
| `app/webhook_receiver/services/queue_service.py` | Modify | Add `Retry(max=3, interval=[60,120,300])` to enqueue call |
| `tests/unit/test_dnc_keywords.py` | Create | 4 keyword scan tests |
| `tests/unit/test_post_call_schemas.py` | Create | 5 Pydantic validation tests |
| `tests/unit/test_post_call_worker.py` | Create | 6 worker unit tests |

---

### Task 1: Add Anthropic dependency + extend settings

**Files:**
- Modify: `requirements.txt`
- Modify: `app/core/settings.py`

- [ ] **Step 1: Add `anthropic` to requirements.txt**

Open `requirements.txt` and add after the existing `rq==1.16.1` line:

```
anthropic>=0.25.0
```

- [ ] **Step 2: Install the dependency**

```powershell
pip install anthropic>=0.25.0
```

Expected: installs successfully, `import anthropic` works.

- [ ] **Step 3: Add `ANTHROPIC_API_KEY` to settings**

In `app/core/settings.py`, add the field after `WEBHOOK_PORT` and extend the existing `model_validator` to also warn on empty API key:

```python
# app/core/settings.py
import logging
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

_logger = logging.getLogger(__name__)


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
    RETELL_WEBHOOK_SECRET: str = Field(
        default="",
        description="Retell AI webhook signing secret for HMAC-SHA256 verification — MUST be set in production"
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL for replay protection and RQ queue"
    )
    WEBHOOK_PORT: int = Field(
        default=8001,
        description="Port for the webhook receiver FastAPI app"
    )
    ANTHROPIC_API_KEY: str = Field(
        default="",
        description="Anthropic API key for Claude Sonnet post-call analysis — MUST be set in production"
    )

    @model_validator(mode="after")
    def warn_if_secrets_empty(self) -> "Settings":
        if not self.RETELL_WEBHOOK_SECRET:
            _logger.warning(
                "RETELL_WEBHOOK_SECRET is not set — webhook signature verification will fail in production"
            )
        if not self.ANTHROPIC_API_KEY:
            _logger.warning(
                "ANTHROPIC_API_KEY is not set — post-call analysis will fail in production"
            )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
```

- [ ] **Step 4: Smoke test settings import**

```powershell
python -c "from app.core.settings import settings; print('ANTHROPIC_API_KEY field exists:', hasattr(settings, 'ANTHROPIC_API_KEY'))"
```

Expected: `ANTHROPIC_API_KEY field exists: True`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt app/core/settings.py
git commit -m "feat: add anthropic dependency and ANTHROPIC_API_KEY setting"
```

---

### Task 2: Module scaffolding + DNC keywords (TDD)

**Files:**
- Create: `app/post_call_analysis/__init__.py`
- Create: `app/post_call_analysis/dnc_keywords.py`
- Create: `tests/unit/test_dnc_keywords.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_dnc_keywords.py`:

```python
# tests/unit/test_dnc_keywords.py
import pytest
from app.post_call_analysis.dnc_keywords import DNC_PHRASES, scan


def test_do_not_call_triggers_scan():
    assert scan("Please do not call me again") is True


def test_remove_me_triggers_scan():
    assert scan("Just remove me from your list please") is True


def test_case_insensitive_matching():
    assert scan("DO NOT CALL me ever") is True


def test_neutral_transcript_does_not_trigger():
    assert scan("I might be interested, call me back tomorrow") is False


def test_all_phrases_trigger():
    for phrase in DNC_PHRASES:
        assert scan(f"The caller said: {phrase}") is True, f"Phrase not matched: {phrase!r}"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/unit/test_dnc_keywords.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create package marker**

Create `app/post_call_analysis/__init__.py` (empty file).

- [ ] **Step 4: Implement `dnc_keywords.py`**

Create `app/post_call_analysis/dnc_keywords.py`:

```python
# app/post_call_analysis/dnc_keywords.py

DNC_PHRASES: frozenset[str] = frozenset({
    "do not call",
    "don't call",
    "stop calling",
    "remove me",
    "remove my number",
    "take me off",
    "unsubscribe",
    "opt out",
    "not interested ever",
    "never call again",
    "don't contact",
    "do not contact",
})


def scan(transcript: str) -> bool:
    """Return True if transcript contains any DNC phrase (case-insensitive)."""
    lower = transcript.lower()
    return any(phrase in lower for phrase in DNC_PHRASES)
```

- [ ] **Step 5: Run tests to verify they pass**

```powershell
python -m pytest tests/unit/test_dnc_keywords.py -v
```

Expected: 5 PASSED

- [ ] **Step 6: Commit**

```bash
git add app/post_call_analysis/__init__.py app/post_call_analysis/dnc_keywords.py tests/unit/test_dnc_keywords.py
git commit -m "feat: add post_call_analysis module scaffold and DNC keyword scanner"
```

---

### Task 3: ExtractionResult schema (TDD)

**Files:**
- Create: `app/post_call_analysis/schemas.py`
- Create: `tests/unit/test_post_call_schemas.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_post_call_schemas.py`:

```python
# tests/unit/test_post_call_schemas.py
import pytest
from pydantic import ValidationError
from app.post_call_analysis.schemas import ExtractionResult


VALID_DATA = {
    "call_outcome": "interested",
    "callback_time": None,
    "objections_raised": ["price too high"],
    "next_action": "Schedule follow-up call",
    "summary": "Lead expressed interest but raised price concerns.",
    "sentiment_reason": "Positive tone throughout; expressed genuine interest.",
    "lead_temperature": "warm",
    "sentiment": "positive",
    "dnc_requested": False,
}


def test_valid_extraction_result_passes():
    result = ExtractionResult(**VALID_DATA)
    assert result.call_outcome == "interested"
    assert result.sentiment == "positive"
    assert result.dnc_requested is False


def test_callback_time_none_is_valid():
    result = ExtractionResult(**{**VALID_DATA, "callback_time": None})
    assert result.callback_time is None


def test_empty_objections_list_is_valid():
    result = ExtractionResult(**{**VALID_DATA, "objections_raised": []})
    assert result.objections_raised == []


def test_missing_required_field_raises():
    data = {k: v for k, v in VALID_DATA.items() if k != "call_outcome"}
    with pytest.raises(ValidationError):
        ExtractionResult(**data)


def test_invalid_call_outcome_raises():
    with pytest.raises(ValidationError):
        ExtractionResult(**{**VALID_DATA, "call_outcome": "maybe"})


def test_invalid_sentiment_raises():
    with pytest.raises(ValidationError):
        ExtractionResult(**{**VALID_DATA, "sentiment": "very_positive"})


def test_invalid_lead_temperature_raises():
    with pytest.raises(ValidationError):
        ExtractionResult(**{**VALID_DATA, "lead_temperature": "lukewarm"})


def test_model_dump_returns_dict():
    result = ExtractionResult(**VALID_DATA)
    dumped = result.model_dump()
    assert isinstance(dumped, dict)
    assert dumped["call_outcome"] == "interested"
    assert dumped["dnc_requested"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/unit/test_post_call_schemas.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `schemas.py`**

Create `app/post_call_analysis/schemas.py`:

```python
# app/post_call_analysis/schemas.py
from typing import Literal
from pydantic import BaseModel


class ExtractionResult(BaseModel):
    call_outcome: Literal[
        "interested",
        "not_interested",
        "callback_requested",
        "dnc_request",
        "no_answer",
        "other",
    ]
    callback_time: str | None
    objections_raised: list[str]
    next_action: str
    summary: str
    sentiment_reason: str
    lead_temperature: Literal["hot", "warm", "cold"]
    sentiment: Literal["positive", "neutral", "negative"]
    dnc_requested: bool
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/unit/test_post_call_schemas.py -v
```

Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/post_call_analysis/schemas.py tests/unit/test_post_call_schemas.py
git commit -m "feat: add ExtractionResult Pydantic schema for Claude structured output"
```

---

### Task 4: Prompts module

**Files:**
- Create: `app/post_call_analysis/prompts.py`

No TDD for this task — it is pure string constants. Correctness is validated end-to-end when the worker runs.

- [ ] **Step 1: Create `prompts.py`**

Create `app/post_call_analysis/prompts.py`:

```python
# app/post_call_analysis/prompts.py

SYSTEM_PROMPT = """You are a post-call analysis assistant for an outbound sales AI system.
Your task is to extract structured information from call transcripts between an AI sales agent and a lead.

Guidelines:
- call_outcome: classify the primary outcome of the call
  - "interested": lead expressed genuine interest in the product/service
  - "not_interested": lead clearly declined
  - "callback_requested": lead asked to be called back at a specific time
  - "dnc_request": lead explicitly asked not to be called again
  - "no_answer": call connected but lead was not reachable or call dropped immediately
  - "other": does not fit any above category
- dnc_requested: ONLY set true if the caller explicitly and unambiguously asked to be removed
  (e.g. "remove me", "don't call again", "take me off your list"). Vague disinterest is NOT a DNC request.
- callback_time: capture verbatim if mentioned (e.g. "tomorrow afternoon", "next Monday 2pm").
  Set to null if no callback was requested.
- objections_raised: list each distinct objection type mentioned. Use short phrases.
  Empty list if no objections were raised.
- lead_temperature: hot = strong buying signals and urgency, warm = interested but hesitant,
  cold = clearly not interested or disengaged.
- summary: 1-2 sentences capturing the key outcome and next step.
- sentiment_reason: brief explanation for why you assigned the given sentiment.
"""


def build_user_message(raw_transcript: str) -> str:
    """Build the user message to send to Claude with the transcript."""
    return (
        "Analyse the following call transcript and extract the requested information.\n\n"
        f"TRANSCRIPT:\n{raw_transcript}"
    )
```

- [ ] **Step 2: Smoke test import**

```powershell
python -c "from app.post_call_analysis.prompts import SYSTEM_PROMPT, build_user_message; print('OK', len(SYSTEM_PROMPT))"
```

Expected: `OK` followed by a character count > 0

- [ ] **Step 3: Commit**

```bash
git add app/post_call_analysis/prompts.py
git commit -m "feat: add Claude system prompt and user message template"
```

---

### Task 5: Worker + queue_service retry config (TDD)

**Files:**
- Create: `tests/unit/test_post_call_worker.py`
- Create: `app/post_call_analysis/worker.py`
- Modify: `app/webhook_receiver/services/queue_service.py`

- [ ] **Step 1: Write the failing worker tests**

Create `tests/unit/test_post_call_worker.py`:

```python
# tests/unit/test_post_call_worker.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.post_call_analysis.worker import _run_analysis, analyze_call
from app.post_call_analysis.schemas import ExtractionResult

SAMPLE_EXTRACTION = ExtractionResult(
    call_outcome="interested",
    callback_time=None,
    objections_raised=["price"],
    next_action="Schedule follow-up",
    summary="Lead expressed interest but raised price concerns.",
    sentiment_reason="Positive tone throughout.",
    lead_temperature="warm",
    sentiment="positive",
    dnc_requested=False,
)

DNC_EXTRACTION = ExtractionResult(
    call_outcome="dnc_request",
    callback_time=None,
    objections_raised=[],
    next_action="No further action",
    summary="Lead asked to be removed from call list.",
    sentiment_reason="Hostile and frustrated.",
    lead_temperature="cold",
    sentiment="negative",
    dnc_requested=True,
)


def _make_session_factory(transcript=None, call_obj=None, lead=None):
    """Build mock session factory returning given DB objects from execute()."""
    call_id = uuid.uuid4()

    if transcript is None:
        transcript = MagicMock()
        transcript.call_id = call_id
        transcript.raw_transcript = "Agent: Hi. User: Sounds interesting."

    if call_obj is None:
        call_obj = MagicMock()
        call_obj.id = call_id
        call_obj.lead_id = uuid.uuid4()

    if lead is None:
        lead = MagicMock()
        lead.id = call_obj.lead_id
        lead.phone_number = "+15551234567"

    # Read session: three execute() calls in order (transcript, call, lead)
    read_session = AsyncMock()
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = transcript
    r2 = MagicMock(); r2.scalar_one_or_none.return_value = call_obj
    r3 = MagicMock(); r3.scalar_one_or_none.return_value = lead
    read_session.execute = AsyncMock(side_effect=[r1, r2, r3])

    read_cm = AsyncMock()
    read_cm.__aenter__ = AsyncMock(return_value=read_session)
    read_cm.__aexit__ = AsyncMock(return_value=False)

    # Write session
    write_session = AsyncMock()
    write_session.execute = AsyncMock()
    begin_cm = AsyncMock()
    begin_cm.__aenter__ = AsyncMock(return_value=None)
    begin_cm.__aexit__ = AsyncMock(return_value=False)
    write_session.begin = MagicMock(return_value=begin_cm)

    write_cm = AsyncMock()
    write_cm.__aenter__ = AsyncMock(return_value=write_session)
    write_cm.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(side_effect=[read_cm, write_cm])
    return factory, transcript, call_obj, lead, write_session


@pytest.mark.asyncio
async def test_happy_path_executes_transcript_update():
    factory, transcript, call_obj, lead, write_session = _make_session_factory()

    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude", return_value=SAMPLE_EXTRACTION):
            with patch("app.post_call_analysis.worker.scan", return_value=False):
                await _run_analysis(str(transcript.call_id))

    # Only one write (UPDATE Transcript) — no DNC
    assert write_session.execute.call_count == 1


@pytest.mark.asyncio
async def test_dnc_from_claude_performs_three_writes():
    factory, transcript, call_obj, lead, write_session = _make_session_factory()

    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude", return_value=DNC_EXTRACTION):
            with patch("app.post_call_analysis.worker.scan", return_value=False):
                await _run_analysis(str(transcript.call_id))

    # Three writes: UPDATE transcript, INSERT dnc_registry, UPDATE leads
    assert write_session.execute.call_count == 3


@pytest.mark.asyncio
async def test_keyword_dnc_overrides_claude_false():
    factory, transcript, call_obj, lead, write_session = _make_session_factory()
    transcript.raw_transcript = "Please remove me from your list"

    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude", return_value=SAMPLE_EXTRACTION):
            with patch("app.post_call_analysis.worker.scan", return_value=True):
                await _run_analysis(str(transcript.call_id))

    # Keyword scan triggered DNC — three writes
    assert write_session.execute.call_count == 3


@pytest.mark.asyncio
async def test_transcript_not_found_skips_claude():
    call_id = uuid.uuid4()

    read_session = AsyncMock()
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = None
    read_session.execute = AsyncMock(return_value=r1)

    read_cm = AsyncMock()
    read_cm.__aenter__ = AsyncMock(return_value=read_session)
    read_cm.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=read_cm)

    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude") as mock_claude:
            await _run_analysis(str(call_id))
            mock_claude.assert_not_called()


def test_analyze_call_raises_on_failure_so_rq_can_retry():
    with patch("app.post_call_analysis.worker.asyncio.run", side_effect=Exception("Claude timeout")):
        with patch("app.post_call_analysis.worker.get_current_job", return_value=MagicMock(retries_left=1)):
            with pytest.raises(Exception, match="Claude timeout"):
                analyze_call("some-call-id")


def test_analyze_call_writes_failure_flag_on_last_retry():
    mock_job = MagicMock()
    mock_job.retries_left = 0

    # First asyncio.run (_run_analysis) raises; second (_write_failure_flag) succeeds
    with patch("app.post_call_analysis.worker.asyncio.run",
               side_effect=[Exception("Claude down"), None]) as mock_run:
        with patch("app.post_call_analysis.worker.get_current_job", return_value=mock_job):
            with pytest.raises(Exception, match="Claude down"):
                analyze_call("some-call-id")

    assert mock_run.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/unit/test_post_call_worker.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `worker.py`**

Create `app/post_call_analysis/worker.py`:

```python
# app/post_call_analysis/worker.py
import asyncio
import logging
import uuid
from datetime import datetime, timezone

import anthropic
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from rq import get_current_job

from app.core.settings import settings
from app.db.session import init_session_factory
from app.models.call import Call
from app.models.contact import Contact, ContactStatus
from app.models.dnc_entry import DNCEntry, DNCSource
from app.models.transcript import Transcript, SentimentLevel
from app.post_call_analysis.dnc_keywords import scan
from app.post_call_analysis.prompts import SYSTEM_PROMPT, build_user_message
from app.post_call_analysis.schemas import ExtractionResult

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-6"


def _call_claude(raw_transcript: str) -> ExtractionResult:
    """Call Claude Sonnet with tool use to extract structured call data."""
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    schema = ExtractionResult.model_json_schema()
    schema.pop("title", None)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(raw_transcript)}],
        tools=[{
            "name": "extract_call_data",
            "description": "Extract structured data from a call transcript for sales analytics",
            "input_schema": schema,
        }],
        tool_choice={"type": "any"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return ExtractionResult(**block.input)

    raise ValueError(
        f"Claude did not return a tool_use block; stop_reason={response.stop_reason}"
    )


async def _write_failure_flag(call_id_str: str, exc: Exception) -> None:
    """Write dead-letter flag to structured_data after all retries are exhausted."""
    try:
        call_id = uuid.UUID(call_id_str)
        session_factory = await init_session_factory()
        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    sa.update(Transcript)
                    .where(Transcript.call_id == call_id)
                    .values(structured_data={
                        "failed_analysis": True,
                        "error": str(exc),
                        "failed_at": datetime.now(tz=timezone.utc).isoformat(),
                    })
                )
        logger.error(
            "analyze_call exhausted all retries — dead-letter flag written",
            extra={"call_id": call_id_str, "error": str(exc)},
        )
    except Exception as write_exc:
        logger.error(
            "Failed to write dead-letter flag",
            extra={"call_id": call_id_str, "error": str(write_exc)},
        )


async def _run_analysis(call_id_str: str) -> None:
    """Async orchestration: load → Claude → DNC scan → write."""
    call_id = uuid.UUID(call_id_str)
    session_factory = await init_session_factory()

    # --- Load transcript + call + lead ---
    async with session_factory() as session:
        result = await session.execute(
            sa.select(Transcript).where(Transcript.call_id == call_id)
        )
        transcript = result.scalar_one_or_none()

        if transcript is None:
            logger.error("Transcript not found", extra={"call_id": call_id_str})
            return

        call_result = await session.execute(
            sa.select(Call).where(Call.id == transcript.call_id)
        )
        call = call_result.scalar_one_or_none()

        lead_phone: str | None = None
        lead_id: uuid.UUID | None = None

        if call is not None:
            lead_result = await session.execute(
                sa.select(Contact).where(Contact.id == call.lead_id)
            )
            lead = lead_result.scalar_one_or_none()
            if lead is not None:
                lead_phone = lead.phone_number
                lead_id = lead.id

    raw = transcript.raw_transcript or ""

    # --- Claude structured extraction ---
    extraction = _call_claude(raw)

    # --- DNC safety scan (OR logic: Claude flag OR keyword match) ---
    dnc_requested = extraction.dnc_requested or scan(raw)

    # --- Write results in a single transaction ---
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                sa.update(Transcript)
                .where(Transcript.call_id == call_id)
                .values(
                    structured_data=extraction.model_dump(),
                    sentiment=SentimentLevel[extraction.sentiment.upper()],
                )
            )

            if dnc_requested and lead_phone and lead_id:
                await session.execute(
                    pg_insert(DNCEntry)
                    .values(phone_number=lead_phone, source=DNCSource.CALLER_REQUEST)
                    .on_conflict_do_nothing(index_elements=["phone_number"])
                )
                await session.execute(
                    sa.update(Contact)
                    .where(Contact.id == lead_id)
                    .values(status=ContactStatus.FAILED_DNC)
                )

    logger.info(
        "analyze_call complete",
        extra={"call_id": call_id_str, "dnc_requested": dnc_requested},
    )


def analyze_call(call_id: str) -> None:
    """RQ job: extract structured data from call transcript using Claude Sonnet.

    Raises on failure so RQ can retry. On last retry, writes dead-letter flag to
    structured_data before re-raising.
    """
    try:
        asyncio.run(_run_analysis(call_id))
    except Exception as exc:
        job = get_current_job()
        if job is not None and getattr(job, "retries_left", 1) == 0:
            asyncio.run(_write_failure_flag(call_id, exc))
        raise
```

- [ ] **Step 4: Run worker tests to verify they pass**

```powershell
python -m pytest tests/unit/test_post_call_worker.py -v
```

Expected: 6 PASSED

- [ ] **Step 5: Update `queue_service.py` to add retry config**

Read `app/webhook_receiver/services/queue_service.py` and replace the `_enqueue_sync` function body to add retry config. The full updated file:

```python
# app/webhook_receiver/services/queue_service.py
import asyncio
import logging
from uuid import UUID

import redis as sync_redis
from rq import Queue, Retry

logger = logging.getLogger(__name__)

POST_CALL_ANALYSIS_JOB = "app.post_call_analysis.worker.analyze_call"


def _enqueue_sync(redis_url: str, call_id: str) -> None:
    conn = sync_redis.from_url(redis_url)
    try:
        q = Queue(connection=conn)
        q.enqueue(
            POST_CALL_ANALYSIS_JOB,
            call_id=call_id,
            retry=Retry(max=3, interval=[60, 120, 300]),
        )
    finally:
        conn.close()


async def enqueue_analysis(redis_url: str, call_id: UUID) -> None:
    try:
        await asyncio.to_thread(_enqueue_sync, redis_url, str(call_id))
        logger.info("enqueued post_call_analysis job", extra={"call_id": str(call_id)})
    except Exception as exc:
        logger.error(
            "failed to enqueue post_call_analysis job",
            extra={"call_id": str(call_id), "error": str(exc)},
        )
```

- [ ] **Step 6: Run the full webhook service test suite to check no regressions**

```powershell
python -m pytest tests/unit/test_webhook_services.py -v
```

Expected: all PASSED (queue_service tests still pass)

- [ ] **Step 7: Smoke test worker import**

```powershell
python -c "from app.post_call_analysis.worker import analyze_call; print('analyze_call importable:', callable(analyze_call))"
```

Expected: `analyze_call importable: True`

- [ ] **Step 8: Commit**

```bash
git add app/post_call_analysis/worker.py app/webhook_receiver/services/queue_service.py tests/unit/test_post_call_worker.py
git commit -m "feat: add post-call analysis worker with Claude Sonnet extraction and DNC handling"
```

---

### Task 6: README + final verification

**Files:**
- Create: `app/post_call_analysis/README.md`

- [ ] **Step 1: Create README**

Create `app/post_call_analysis/README.md`:

```markdown
# Post-Call Analysis

RQ background worker that processes call transcripts using Claude Sonnet and writes structured extraction results to PostgreSQL.

## Running the Worker

```bash
rq worker --with-scheduler default
```

The worker listens on the `default` queue and processes `analyze_call` jobs enqueued by the webhook receiver on `call_analyzed` events.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude Sonnet API key |
| `DATABASE_URL` | Yes | PostgreSQL async URL |
| `REDIS_URL` | No | Redis URL (default: `redis://localhost:6379`) |

## Job: `analyze_call(call_id: str)`

**Trigger:** Enqueued by `app/webhook_receiver/services/queue_service.py` when a `call_analyzed` webhook event is received.

**Retry:** 3 attempts with backoff (60s → 120s → 300s). On exhaustion, writes `{"failed_analysis": true, "error": "..."}` to `call_transcripts.structured_data`.

**Flow:**
1. Load `call_transcripts` row by `call_id` UUID
2. Load associated `call_logs` and `leads` rows
3. Call Claude Sonnet (`claude-sonnet-4-6`) with the raw transcript
4. Run DNC keyword scan as safety net
5. Write `structured_data` + `sentiment` to `call_transcripts`
6. If DNC detected: insert into `dnc_registry`, set `leads.status = failed_dnc`

## Extracted Fields (`structured_data` JSONB)

| Field | Type | Description |
|---|---|---|
| `call_outcome` | string | `interested` / `not_interested` / `callback_requested` / `dnc_request` / `no_answer` / `other` |
| `callback_time` | string \| null | Verbatim callback time if mentioned |
| `objections_raised` | list[string] | Distinct objection types |
| `next_action` | string | Recommended next step |
| `summary` | string | 1-2 sentence call summary |
| `sentiment_reason` | string | Explanation for sentiment classification |
| `lead_temperature` | string | `hot` / `warm` / `cold` |
| `sentiment` | string | `positive` / `neutral` / `negative` |
| `dnc_requested` | bool | Claude's DNC flag (OR'd with keyword scan) |

## DNC Detection

Two-layer approach for compliance:
1. **Claude flag:** `dnc_requested` in `ExtractionResult` (context-aware)
2. **Keyword scan:** `dnc_keywords.scan(transcript)` — deterministic, auditable fallback

Either layer triggering causes the lead to be added to `dnc_registry` (source: `caller_request`) and their status set to `failed_dnc`.

## Testing

```bash
python -m pytest tests/unit/test_dnc_keywords.py tests/unit/test_post_call_schemas.py tests/unit/test_post_call_worker.py -v
```
```

- [ ] **Step 2: Run the complete post-call-analysis test suite**

```powershell
python -m pytest tests/unit/test_dnc_keywords.py tests/unit/test_post_call_schemas.py tests/unit/test_post_call_worker.py -v
```

Expected: 19 PASSED (5 + 8 + 6)

- [ ] **Step 3: Run the full unit test suite for regressions**

```powershell
python -m pytest tests/unit/ -v --tb=short
```

Expected: all PASSED — no regressions in webhook receiver tests

- [ ] **Step 4: Verify app imports cleanly**

```powershell
python -c "
from app.post_call_analysis.worker import analyze_call
from app.post_call_analysis.schemas import ExtractionResult
from app.post_call_analysis.dnc_keywords import scan
from app.post_call_analysis.prompts import SYSTEM_PROMPT
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 5: Final commit**

```bash
git add app/post_call_analysis/README.md
git commit -m "docs: add post-call analysis developer documentation"
git commit --allow-empty -m "feat: complete post-call analysis module - Claude Sonnet extraction, DNC detection, RQ retry, dead-letter flag"
```

---

## Dependency Notes

- `analyze_call` job path `app.post_call_analysis.worker.analyze_call` must exactly match `POST_CALL_ANALYSIS_JOB` in `queue_service.py`
- `call_id` is passed as a string UUID by `queue_service.py` — converted to `uuid.UUID` at the start of `_run_analysis`
- `SentimentLevel` values in the DB are lowercase strings (`"positive"`, `"neutral"`, `"negative"`) — `ExtractionResult.sentiment` matches this directly; `SentimentLevel[extraction.sentiment.upper()]` uses the enum key
- Claude tool use response: take the first `tool_use` block; ignore any `text` blocks
- `pg_insert(DNCEntry).on_conflict_do_nothing(index_elements=["phone_number"])` requires PostgreSQL dialect — correct for this project
