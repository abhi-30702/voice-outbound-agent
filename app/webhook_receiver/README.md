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
