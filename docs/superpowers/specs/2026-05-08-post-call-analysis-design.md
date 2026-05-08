# Post-Call Analysis — Design Spec
# Module 4 (Session scope: post-call-analysis)
# Date: 2026-05-08

---

## Goal

Build an RQ worker that consumes `analyze_call` jobs enqueued by the webhook receiver on `call_analyzed` events. The worker loads the raw transcript from PostgreSQL, calls Claude Sonnet to extract structured call data, runs a keyword-based DNC safety scan, writes results back to `call_transcripts.structured_data` (JSONB) and `call_transcripts.sentiment`, and handles DNC side-effects (insert into `dnc_registry`, set lead `FAILED_DNC`).

---

## Scope

**In scope:**
- RQ worker function `analyze_call(call_id: str)` at `app/post_call_analysis/worker.py`
- Claude Sonnet structured extraction via Anthropic SDK (tool use / structured output)
- Pydantic v2 output schema (`ExtractionResult`)
- DNC detection: Claude flag + keyword scan safety net (OR logic)
- DB writes: `structured_data`, `sentiment`, `dnc_registry` insert, lead `FAILED_DNC`
- RQ retry: 3 attempts with backoff (60s, 120s, 300s)
- Dead-letter: write `{"failed_analysis": true, "error": "..."}` to `structured_data` on exhaustion
- `ANTHROPIC_API_KEY` added to `app/core/settings.py`
- Full TDD test suite

**Out of scope:**
- Dashboard surfacing of failed analyses (Module 7)
- n8n trigger after analysis (Module 8)
- Conversation prompt tuning (Module 6)
- Docker deployment (Module 9)

---

## Architecture

### Approach: Single orchestration worker + separated concerns

`worker.py` owns the RQ job and linear orchestration. Prompts, output schema, and DNC keywords live in their own modules — the parts most likely to evolve independently as extraction quality is tuned and compliance requirements change.

```
app/post_call_analysis/
├── __init__.py
├── worker.py        — RQ job: analyze_call(call_id), retry config, dead-letter
├── prompts.py       — Claude system prompt + user message template
├── schemas.py       — Pydantic ExtractionResult model
└── dnc_keywords.py  — DNC phrase list + scan(transcript) -> bool
```

---

## Data Flow

```
RQ dequeues analyze_call(call_id: str)
  │
  ├── Load Transcript + Call + Lead from DB by call_id (UUID)
  │    └── if transcript not found: log ERROR, return (job is a no-op)
  │
  ├── Call Claude Sonnet (prompts.py → Anthropic SDK)
  │    └── Parse response → ExtractionResult (schemas.py)
  │
  ├── Run dnc_keywords.scan(raw_transcript) → keyword_dnc: bool
  │
  ├── Merge DNC: dnc_requested = result.dnc_requested OR keyword_dnc
  │
  ├── Write to DB (single transaction):
  │    ├── call_transcripts.structured_data = result.model_dump()
  │    ├── call_transcripts.sentiment = SentimentEnum[result.sentiment.upper()]
  │    └── if dnc_requested:
  │         ├── INSERT INTO dnc_registry (phone_number, source=CALLER_REQUEST)
  │         │    ON CONFLICT (phone_number) DO NOTHING
  │         └── UPDATE leads SET status = FAILED_DNC WHERE id = lead_id
  │
  └── On any exception before DB write:
       RQ retries up to 3× (60s → 120s → 300s backoff) — job raises, RQ catches and re-enqueues
       On exhaustion: RQ calls on_failure callback → write {"failed_analysis": true, "error": str(exc)}
                      to structured_data; leave sentiment NULL
```

---

## Structured Output Schema

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
    callback_time: str | None          # free-form, e.g. "tomorrow 3pm"; None if not requested
    objections_raised: list[str]       # e.g. ["too expensive", "bad timing"]
    next_action: str                   # e.g. "Schedule follow-up", "No further action"
    summary: str                       # 1-2 sentence plain-English call summary
    sentiment_reason: str              # explanation for the sentiment classification
    lead_temperature: Literal["hot", "warm", "cold"]
    sentiment: Literal["positive", "neutral", "negative"]
    dnc_requested: bool                # true if caller clearly asked not to be called again
```

`structured_data` in PostgreSQL stores `result.model_dump()` verbatim. The `sentiment` field maps to the existing `SentimentEnum` (POSITIVE / NEUTRAL / NEGATIVE) on the `Transcript` model.

---

## Claude Integration

**Model:** `claude-sonnet-4-6` (pinned constant in `worker.py`)

**Sync/async bridge:** RQ workers are synchronous. The job function uses `asyncio.run()` to call an async inner function that handles all DB operations via SQLAlchemy async session. The Anthropic SDK client is synchronous (`anthropic.Anthropic`, not `AsyncAnthropic`).

**Approach:** Anthropic SDK `client.messages.create()` with a `tools` parameter defining the `ExtractionResult` schema — forces Claude to return valid JSON matching the schema. Parse tool use response into `ExtractionResult` via Pydantic.

**System prompt** (`prompts.py`):
- Role: post-call analysis assistant for an outbound sales AI
- Task: extract structured data from a call transcript
- Instructions: be conservative with `dnc_requested` (only true if caller explicitly and unambiguously asked to be removed); `callback_time` should be verbatim if mentioned; `objections_raised` should be a list of distinct objection types

**User message template** (`prompts.py`):
```
Analyse the following call transcript and extract the requested information.

TRANSCRIPT:
{raw_transcript}
```

---

## DNC Detection

Two-layer approach (belt-and-suspenders for compliance):

**Layer 1 — Claude:** `dnc_requested` field in `ExtractionResult`. Claude infers intent from context.

**Layer 2 — Keyword scan** (`dnc_keywords.py`):
```python
DNC_PHRASES = frozenset({
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
    lower = transcript.lower()
    return any(phrase in lower for phrase in DNC_PHRASES)
```

**Merge logic:** `dnc_requested = claude_result.dnc_requested or scan(raw_transcript)`

If either layer flags DNC:
1. `INSERT INTO agent_operations.dnc_registry (phone_number, source) VALUES (:phone, 'caller_request') ON CONFLICT (phone_number) DO NOTHING`
2. `UPDATE agent_operations.leads SET status = 'failed_dnc' WHERE id = :lead_id`

---

## Settings

Add to `app/core/settings.py`:

```python
ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key for Claude Sonnet")
```

With a startup warning (same pattern as `RETELL_WEBHOOK_SECRET`) if empty.

Constant in `worker.py`:
```python
CLAUDE_MODEL = "claude-sonnet-4-6"
```

---

## Error Handling

| Scenario | Response |
|---|---|
| Transcript row not found | Log ERROR, return — job is a no-op |
| Claude API error (timeout, 429, 5xx) | RQ retries up to 3× with 60s/120s/300s backoff |
| Pydantic validation error on Claude response | Treated as Claude failure — retried |
| All retries exhausted | RQ `on_failure` callback writes `{"failed_analysis": true, "error": "..."}` to `structured_data`; sentiment left NULL |
| DNC insert conflict (already in registry) | `ON CONFLICT DO NOTHING` — idempotent |
| DB error during write | Exception propagates — RQ retries |

---

## Testing Strategy

### Unit Tests

**`tests/unit/test_dnc_keywords.py`**
- All DNC phrases trigger `scan()` → True
- Neutral phrases ("call me back", "not available") → False
- Case-insensitive matching works
- Mixed-case transcript matched

**`tests/unit/test_post_call_schemas.py`**
- Valid `ExtractionResult` dict passes validation
- Missing required fields raise `ValidationError`
- Invalid enum values (`call_outcome`, `sentiment`, `lead_temperature`) raise `ValidationError`
- `callback_time=None` is valid
- `objections_raised=[]` is valid

**`tests/unit/test_worker.py`** (mock Anthropic client + mock AsyncSession)
- Happy path: Claude returns valid extraction → `structured_data` written, `sentiment` set
- DNC from Claude: `dnc_requested=True` → `dnc_registry` insert + lead `FAILED_DNC`
- DNC from keyword only: Claude returns `dnc_requested=False`, keyword scan fires → same side-effects
- DNC both: no duplicate DB writes (idempotent)
- Claude API failure: exception raised (RQ handles retry)
- Dead-letter path: after exhaustion, `{"failed_analysis": true}` written to `structured_data`
- Transcript not found: function returns early, no Claude call made

---

## Security & Compliance

- `ANTHROPIC_API_KEY` never logged
- DNC side-effects are idempotent (`ON CONFLICT DO NOTHING`)
- Keyword scan is deterministic and auditable — no LLM involvement for compliance enforcement
- All SQL parameterised (SQLAlchemy bound params)
- `raw_transcript` is already persisted before this job runs — Claude failure never causes data loss

---

## Known Constraints

- Job function path `app.post_call_analysis.worker.analyze_call` must match the path enqueued by `queue_service.py` in the webhook receiver
- `call_id` argument is passed as a string UUID (not UUID object) — convert at job entry
- Claude Sonnet tool-use response may occasionally return multiple tool calls — take the first
- `SentimentEnum` values are uppercase in the DB model (`POSITIVE`, `NEUTRAL`, `NEGATIVE`) — map from Claude's lowercase output

---

*Last updated: 2026-05-08*
*Module: post-call-analysis (PRD Module 5, session Module 4)*
