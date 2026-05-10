# n8n Flows Design

**Date:** 2026-05-09
**Module:** 8 (n8n-flows)
**Status:** Approved

---

## 1. Goal

Add post-call automation to the outbound agent. After `analyze_call` (the RQ job in Module 4) writes structured extraction data to `call_transcripts.structured_data`, it notifies a self-hosted n8n instance via a single webhook POST. n8n then orchestrates three downstream actions:

1. **Google Sheets** — append one row per call (always)
2. **Telnyx SMS** — send a follow-up SMS when `call_outcome` is `interested` or `callback_requested`
3. **Google Calendar** — create a callback event when `callback_requested == true` and `callback_time` is not null

The analysis job is never blocked by automation failures. n8n is fully disableable via env var.

---

## 2. Architecture

```
analyze_call (RQ worker)
    │  writes structured_data → call_transcripts (DB)
    │  POST http://n8n:5678/webhook/post-call
    │  (fire-and-forget, 5s timeout, X-Internal-Webhook-Secret header)
    ▼
n8n Webhook Trigger
    │
    ├─► Google Sheets (always) — append one row
    │
    ├─► IF call_outcome in [interested, callback_requested]
    │       └─► Telnyx SMS (HTTP Request node)
    │
    └─► IF callback_requested == true AND callback_time != null
            └─► Google Calendar — create 30-min event
```

**Dependency direction:** `app/post_call_analysis/worker.py` → n8n. No reverse dependency. n8n never calls back into FastAPI.

**Resilience:** DB writes complete before n8n is notified. An exception in `_notify_n8n` is caught, logged as a warning, and never re-raised. The `analyze_call` RQ job always succeeds or fails on its own merits.

**Idempotency:** `call_id` (UUID) is included in every webhook payload. n8n flows can use it to deduplicate if re-triggered.

---

## 3. Worker Changes — `app/post_call_analysis/worker.py`

### New function: `_notify_n8n`

```python
async def _notify_n8n(payload: dict) -> None:
    url = settings.N8N_WEBHOOK_URL
    secret = settings.N8N_WEBHOOK_SECRET
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                url,
                json=payload,
                headers={"X-Internal-Webhook-Secret": secret},
            )
    except Exception as exc:
        logger.warning("n8n notify failed", extra={"error": str(exc)})
```

### Payload assembled at end of `_run_analysis` (after both DB writes):

```python
await _notify_n8n({
    "call_id": str(call_id),
    "lead_id": str(lead_id),
    "phone_number": lead_phone,
    "first_name": lead.first_name,
    "last_name": lead.last_name,
    "company": lead.company,
    "call_outcome": extraction.call_outcome,
    "callback_requested": extraction.call_outcome == "callback_requested",
    "callback_time": extraction.callback_time,
    "summary": extraction.summary,
    "lead_temperature": extraction.lead_temperature,
    "sentiment": extraction.sentiment,
    "objections_raised": extraction.objections_raised,
    "next_action": extraction.next_action,
})
```

`callback_requested` is derived from `extraction.call_outcome == "callback_requested"` since `ExtractionResult` does not have a separate boolean field for it.

### New dependency

`httpx` — added to `requirements.txt`. Already present in most FastAPI projects; verify before adding.

---

## 4. New Settings — `app/core/settings.py`

```python
N8N_WEBHOOK_URL: str = ""       # empty = automation disabled
N8N_WEBHOOK_SECRET: str = ""    # shared secret for X-Internal-Webhook-Secret header
```

---

## 5. n8n Flow — `n8n-flows/post-call-automation.json`

### Node sequence

| # | Node | Type | Behaviour |
|---|------|------|-----------|
| 1 | Webhook | Webhook Trigger | POST `/webhook/post-call`; responds `200 OK` immediately |
| 2 | Log to Sheets | Google Sheets (Append) | One row: call_id, phone_number, first_name, last_name, company, call_outcome, lead_temperature, sentiment, summary, callback_time, created_at |
| 3 | Should SMS? | IF | `call_outcome` equals `interested` OR `callback_requested` |
| 4 | Send SMS | HTTP Request | `POST https://api.telnyx.com/v2/messages`; Auth: `Bearer {{ $env.TELNYX_API_KEY }}`; body: `{from: TELNYX_FROM_NUMBER, to: phone_number, text: "Hi {first_name}, thanks for speaking with us today. {next_action}."}` |
| 5 | Should book? | IF | `callback_requested` equals `true` AND `callback_time` is not empty |
| 6 | Create Calendar Event | Google Calendar | Title: `Callback: {first_name} {last_name}`, start: `callback_time`, duration: 30 min, description: `summary` |

Nodes 3 and 5 both branch from node 2's output (parallel paths). The `false` branch of each IF terminates — no further action.

### Credentials required (configured in n8n UI after import)

| Credential | Used by |
|------------|---------|
| Google Sheets OAuth2 | Node 2 |
| Google Calendar OAuth2 | Node 6 |
| Telnyx API key (HTTP header) | Node 4 |

### n8n environment variables (set in n8n container or UI)

| Variable | Purpose |
|----------|---------|
| `TELNYX_API_KEY` | Bearer token for Telnyx Messages API |
| `TELNYX_FROM_NUMBER` | E.164 sender number |
| `GOOGLE_SHEET_ID` | Target spreadsheet ID |
| `GOOGLE_CALENDAR_ID` | Target calendar ID (e.g. `primary`) |

---

## 6. Docker Compose

### New `n8n` service

```yaml
n8n:
  image: n8nio/n8n:latest
  ports:
    - "5678:5678"
  environment:
    N8N_HOST: localhost
    N8N_PORT: 5678
    N8N_PROTOCOL: http
    WEBHOOK_URL: http://localhost:5678/
    N8N_BASIC_AUTH_ACTIVE: "true"
    N8N_BASIC_AUTH_USER: admin
    N8N_BASIC_AUTH_PASSWORD: admin
  volumes:
    - n8n_data:/home/node/.n8n
  depends_on:
    - api
```

Add `n8n_data:` to the top-level `volumes:` block.

### `api` service — new env vars

```yaml
N8N_WEBHOOK_URL: http://n8n:5678/webhook/post-call
N8N_WEBHOOK_SECRET: changeme
```

---

## 7. File Structure

```
n8n-flows/
├── post-call-automation.json   # n8n flow export (import via n8n UI → Workflows → Import)
└── README.md                   # setup: import steps, credentials, env vars, test curl

app/post_call_analysis/
└── worker.py                   # modified: _notify_n8n added, called at end of _run_analysis

app/core/
└── settings.py                 # modified: N8N_WEBHOOK_URL, N8N_WEBHOOK_SECRET added

docker-compose.yml              # modified: n8n service + n8n_data volume + api env vars
requirements.txt                # modified: httpx added if not present
```

---

## 8. Testing Strategy

Backend only (pytest + pytest-asyncio + respx). No automated tests for the n8n flow itself — manual verification via curl.

| Test file | Coverage |
|-----------|----------|
| `tests/unit/test_n8n_notify.py` | `_notify_n8n` sends correct URL, secret header, JSON payload; skips when URL is empty; swallows HTTP errors (ConnectError, timeout, 500); logs warning on failure |
| `tests/unit/test_worker_notify.py` | `_run_analysis` calls `_notify_n8n` after both DB writes; `_notify_n8n` is not called when analysis raises before DB write; payload includes all required keys with correct types |

**Test dependency:** `respx` — added to `requirements-dev.txt` for httpx mocking.

**Target:** ~10 new tests, total suite ~225.

### Manual verification (documented in `n8n-flows/README.md`)

```bash
curl -X POST http://localhost:5678/webhook/post-call \
  -H "Content-Type: application/json" \
  -H "X-Internal-Webhook-Secret: changeme" \
  -d '{
    "call_id": "00000000-0000-0000-0000-000000000001",
    "lead_id": "00000000-0000-0000-0000-000000000002",
    "phone_number": "+919876543210",
    "first_name": "Ravi",
    "last_name": "Sharma",
    "company": "ABC Corp",
    "call_outcome": "callback_requested",
    "callback_requested": true,
    "callback_time": "2026-05-10T10:00:00+05:30",
    "summary": "Lead asked for a callback next morning.",
    "lead_temperature": "hot",
    "sentiment": "positive",
    "objections_raised": ["too busy"],
    "next_action": "Schedule a callback for tomorrow morning."
  }'
```

Expected: Sheets row appended, SMS sent (visible in Telnyx logs), Calendar event at `callback_time`.

---

## 9. Dependency Notes

- `httpx` — new pip package; used only in `_notify_n8n`; no impact on existing code paths
- `respx` — dev dependency for httpx mocking in tests
- n8n credentials (Google OAuth2, Telnyx) — operator-configured in n8n UI; not stored in code
- No new DB tables or migrations required
- No changes to webhook receiver or dashboard API

---

*Owner: Srinivas / Fidelitus Corp + SherpaVector*
