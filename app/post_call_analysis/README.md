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
