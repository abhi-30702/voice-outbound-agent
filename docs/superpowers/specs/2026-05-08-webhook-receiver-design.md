# Webhook Receiver — Design Spec
# Module 3 (Session scope: webhook-receiver)
# Date: 2026-05-08

---

## Goal

Build a standalone FastAPI service that receives Retell AI webhook events, verifies HMAC signatures, and updates the database for each call lifecycle event. Provides the persistence bridge between Retell AI's call orchestration and the PostgreSQL call log / lead status tables.

---

## Scope

**In scope:**
- Standalone FastAPI app (`app/webhook_receiver/`) on its own port
- HMAC-SHA256 signature verification (`x-retell-signature`) via FastAPI dependency
- Redis-based replay protection (retell_call_id + event_type, 10-minute TTL)
- Handlers for: `call_started`, `call_ended`, `call_analyzed`, `transcript_updated`
- Service layer for all DB operations (transactions, no SQL in handlers)
- RQ job stub enqueue on `call_analyzed` (placeholder for Module 5)
- Structured logging on every event: `event_type`, `retell_call_id`, `lead_id`, `processing_latency_ms`
- Full TDD test suite

**Out of scope:**
- Claude Sonnet post-call extraction (Module 5)
- WebSocket/dashboard broadcasting (Module 8)
- Retell agent configuration / agent CRUD (separate module)
- Docker deployment (Module 10)

---

## Architecture

### Approach: Single endpoint + dependency-injected HMAC

One `POST /webhook` endpoint receives all Retell events. HMAC verification is a FastAPI `Depends()` that reads the raw request body before JSON parsing — ensuring the signature check operates on the exact bytes Retell signed. The dispatcher routes by `event_type`. Handlers are thin orchestrators; all SQL lives in services.

Retell sends all events to a single configured webhook URL, so per-event routing at the HTTP layer is not compatible. Middleware-based HMAC was rejected due to FastAPI body-streaming complexity.

---

## File Structure

```
app/webhook_receiver/
├── __init__.py
├── main.py                       — FastAPI app, lifespan (db + redis init/close)
├── config.py                     — WebhookConfig dataclass (secret, port, redis url)
├── signature_verifier.py         — pure HMAC-SHA256 verification (no FastAPI imports)
├── dependencies.py               — FastAPI Depends: raw body read, sig verify, replay check
├── router.py                     — APIRouter: POST /webhook → dispatcher
├── dispatcher.py                 — dispatches event_type → handler; logs WARNING on unknown
├── schemas/
│   ├── __init__.py
│   ├── base.py                   — BaseRetellEvent: event_type, call_id, timestamp
│   ├── call_started.py           — CallStartedPayload
│   ├── call_ended.py             — CallEndedPayload
│   ├── call_analyzed.py          — CallAnalyzedPayload (includes raw_transcript)
│   └── transcript_updated.py    — TranscriptUpdatedPayload
├── handlers/
│   ├── __init__.py
│   ├── call_started.py           — upsert call_log, set lead status calling
│   ├── call_ended.py             — finalize call_log, set lead completed/failed
│   ├── call_analyzed.py          — write transcript, enqueue RQ analysis stub
│   └── transcript_updated.py    — structured log only, return immediately
├── services/
│   ├── __init__.py
│   ├── call_log_service.py       — upsert(), update_end() on call_logs table
│   ├── lead_service.py           — set_status() on leads table
│   ├── transcript_service.py     — create() on call_transcripts table
│   └── queue_service.py          — enqueue_analysis() RQ stub job
└── README.md
```

---

## Data Flow

```
POST /webhook
  │
  ├─ dependencies.py
  │    ├── read raw body bytes
  │    ├── verify x-retell-signature (HMAC-SHA256, constant-time compare)
  │    ├── check timestamp within 5 minutes → 400 if stale
  │    └── check Redis for (retell_call_id + event_type) → 200 if duplicate
  │
  ├─ router.py
  │    └── parse JSON → BaseRetellEvent, pass to dispatcher
  │
  ├─ dispatcher.py
  │    └── match event_type → call handler
  │         unknown type → log WARNING, return 200
  │
  ├─ handler (thin orchestrator)
  │    └── validate full payload via Pydantic schema
  │         call service(s) inside async with session
  │
  ├─ service(s)
  │    └── execute parameterized SQL in transaction
  │         log structured fields
  │
  └─ return 200 OK (always after safe processing)
       Retell retries on non-2xx; replay protection ensures idempotency
```

---

## Event Handling

### `call_started`
Retell confirms the call connected. Acts as authoritative lifecycle reconciliation point.

**Actions:**
1. `call_log_service.upsert(retell_call_id, lead_id, start_time)` — create row if not exists (dialing worker may have pre-created it), set `start_time` and `retell_call_id`
2. `lead_service.set_status(lead_id, "calling")`

**DB (transaction):**
- `INSERT INTO agent_operations.call_logs (...) ON CONFLICT (retell_call_id) DO UPDATE SET start_time = ...`
- `UPDATE agent_operations.leads SET status = 'calling' WHERE id = :lead_id`

---

### `call_ended`
Call has disconnected. Finalizes telemetry.

**Actions:**
1. `call_log_service.update_end(retell_call_id, end_time, duration_sec, disconnect_reason, recording_url)`
2. `lead_service.set_status(lead_id, status)` — status is `"failed"` if `disconnect_reason` in `{"error", "timeout", "dial_timeout", "dial_failed"}`, otherwise `"completed"`

**DB (transaction):**
- `UPDATE agent_operations.call_logs SET end_time=..., duration_sec=..., disconnect_reason=..., recording_url=... WHERE retell_call_id = :id`
- `UPDATE agent_operations.leads SET status = :status WHERE id = :lead_id`

---

### `call_analyzed`
Retell's analysis is complete (transcript + sentiment available). Hands off to Module 5.

**Actions:**
1. `transcript_service.create(call_id, raw_transcript)` — INSERT into `call_transcripts` with `raw_transcript`, leave `structured_data` NULL
2. `queue_service.enqueue_analysis(call_id)` — enqueue RQ job `post_call_analysis` (stub; Module 5 implements the worker)

**DB (transaction):**
- `INSERT INTO agent_operations.call_transcripts (call_id, raw_transcript) VALUES (:call_id, :raw_transcript)`

**Queue:**
- `rq_queue.enqueue("app.post_call_analysis.worker.analyze_call", call_id=str(call_id))`
- If Redis unavailable: log ERROR, do NOT fail webhook (transcript is persisted; job can be re-enqueued)

---

### `transcript_updated`
Partial transcript update during active call (for live dashboard). Dashboard (Module 8) does not exist yet.

**Actions:**
- Structured log: `event_type`, `retell_call_id`, timestamp
- Return `200 OK` immediately

---

## HMAC Signature Verification

```python
# signature_verifier.py
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

- Uses `hmac.compare_digest` (constant-time) to prevent timing attacks
- `raw_body` is the exact bytes from the request (before JSON parsing)
- Returns bool; dependency raises `HTTPException(403)` on False

---

## Replay Protection

Redis key: `webhook:seen:{retell_call_id}:{event_type}`
TTL: 600 seconds (10 minutes)

On each request (after signature passes):
1. Check if key exists in Redis → if yes, return `200 OK` silently
2. If no, `SET key EX 600` then proceed to handler

This prevents duplicate DB writes from Retell's retry logic.

---

## Config

```python
# config.py
from dataclasses import dataclass
import os

@dataclass
class WebhookConfig:
    RETELL_WEBHOOK_SECRET: str = os.environ["RETELL_WEBHOOK_SECRET"]
    DATABASE_URL: str = os.environ["DATABASE_URL"]
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")
    PORT: int = int(os.environ.get("WEBHOOK_PORT", "8001"))
    TIMESTAMP_TOLERANCE_SECONDS: int = 300  # 5 minutes
```

Reads from environment; fails fast on startup if `RETELL_WEBHOOK_SECRET` or `DATABASE_URL` missing.

---

## Error Handling

| Scenario | Response | Notes |
|---|---|---|
| Invalid HMAC | `403 Forbidden` | Before any DB work |
| Stale timestamp (> 5 min) | `400 Bad Request` | |
| Replay detected | `200 OK` | Silently idempotent |
| Unknown `event_type` | `200 OK` | Log `WARNING` |
| Pydantic validation error | `422 Unprocessable Entity` | Only for known event types |
| DB error in service | `500 Internal Server Error` | Retell retries; replay protection prevents duplicate writes |
| Redis unavailable (replay check) | proceed without replay check | Log `WARNING`; degrade gracefully |
| Redis unavailable (queue_service) | `200 OK` | Log `ERROR`; transcript already persisted |

---

## Testing Strategy

### Unit Tests

**`tests/unit/test_signature_verifier.py`**
- Valid signature passes
- Tampered body fails
- Wrong secret fails
- Correct key: `x-retell-signature` header value, not `Bearer ...`
- `hmac.compare_digest` used (not `==`)

**`tests/unit/test_dispatcher.py`**
- `call_started` → `call_started` handler called
- `call_ended` → `call_ended` handler called
- `call_analyzed` → `call_analyzed` handler called
- `transcript_updated` → `transcript_updated` handler called
- Unknown type → logs WARNING, no exception raised

**`tests/unit/test_schemas.py`**
- Each payload schema validates correct data
- Missing required fields raise `ValidationError`
- Extra fields ignored (Retell may add fields in future)

### Integration Tests

**`tests/integration/test_webhook_router.py`** (FastAPI `TestClient`, mocked services)
- Valid request with correct HMAC → 200
- Invalid HMAC → 403
- Stale timestamp → 400
- Duplicate event (Redis mock) → 200 without calling handler
- `call_started` event → `call_log_service.upsert` and `lead_service.set_status` called
- `call_ended` event → `call_log_service.update_end` and `lead_service.set_status` called
- `call_analyzed` event → `transcript_service.create` and `queue_service.enqueue_analysis` called
- `transcript_updated` event → no service calls, 200 returned
- Unknown event_type → 200, WARNING logged

**`tests/integration/test_services.py`** (real test DB)
- `call_log_service.upsert`: creates new row; idempotent on second call (no duplicate)
- `call_log_service.update_end`: updates correct row by `retell_call_id`
- `lead_service.set_status`: transitions status correctly
- `transcript_service.create`: inserts with `raw_transcript`, NULL `structured_data`
- All service ops wrapped in transactions (rollback on error)

---

## Compliance & Security

- `RETELL_WEBHOOK_SECRET` never logged
- All SQL parameterized (SQLAlchemy bound params)
- HMAC constant-time comparison prevents timing attacks
- Replay protection prevents duplicate lead status transitions
- No DNC writes in this module (that is Module 5's responsibility via `call_outcome == "dnc_request"`)

---

## Known Constraints

- Port 8001 (dialing worker / FastAPI main will use 8000)
- No Retell SDK used — raw webhook payload parsed via Pydantic
- `queue_service` stub job name must match Module 5's final job function path: `app.post_call_analysis.worker.analyze_call`
- Redis required for replay protection; service degrades gracefully if Redis is unavailable

---

*Last updated: 2026-05-08*
*Module: webhook-receiver (PRD Module 4, session Module 3)*
