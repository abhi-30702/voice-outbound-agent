# n8n Flows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the post-call analysis RQ worker to notify a self-hosted n8n instance via a fire-and-forget webhook POST, which then logs every call to Google Sheets, sends a Telnyx SMS for interested/callback leads, and books a Google Calendar event for callback-requested calls with a callback_time.

**Architecture:** After `analyze_call` writes structured extraction data to `call_transcripts`, it calls `_notify_n8n()` — a 5-second-timeout async function that POSTs a JSON payload to n8n and swallows all exceptions. n8n branches on `call_outcome` and `callback_requested`: all paths write to Google Sheets; interested/callback_requested also send SMS; callback_requested + non-empty callback_time also create a Calendar event.

**Tech Stack:** Python 3.13, httpx (already in requirements.txt), respx 0.21 (test mock), pydantic-settings, n8n (Docker: n8nio/n8n:latest), Google Sheets API, Google Calendar API, Telnyx Messages API v2

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/core/settings.py` | Modify | Add `N8N_WEBHOOK_URL` and `N8N_WEBHOOK_SECRET` fields |
| `app/post_call_analysis/worker.py` | Modify | Add `_notify_n8n()`, capture lead fields, call notify at end of `_run_analysis` |
| `requirements.txt` | Modify | Add `respx==0.21.1` |
| `tests/unit/test_n8n_notify.py` | Create | 5 unit tests for `_notify_n8n` in isolation |
| `tests/unit/test_worker_notify.py` | Create | 3 integration tests verifying `_run_analysis` calls `_notify_n8n` correctly |
| `docker-compose.yml` | Modify | Add `n8n` service, `n8n_data` volume, two env vars on `api` service |
| `n8n-flows/post-call-automation.json` | Create | Importable n8n flow export (6 nodes, pre-wired) |
| `n8n-flows/README.md` | Create | Setup instructions: import, credentials, env vars, test curl |

---

## Task 1: New settings + test dependency

**Files:**
- Modify: `app/core/settings.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add `respx` to requirements.txt**

Open `requirements.txt` and append:

```
respx==0.21.1
```

Install it:
```powershell
.venv\Scripts\pip install respx==0.21.1
```

Expected output: `Successfully installed respx-0.21.1`

- [ ] **Step 2: Add two new settings fields to `app/core/settings.py`**

Add these two fields directly after the `ANTHROPIC_API_KEY` field (before the `@model_validator`):

```python
    N8N_WEBHOOK_URL: str = Field(
        default="",
        description="n8n webhook URL for post-call automation — empty string disables automation"
    )
    N8N_WEBHOOK_SECRET: str = Field(
        default="",
        description="Shared secret sent in X-Internal-Webhook-Secret header to n8n"
    )
```

Do NOT add a warning for these fields in `warn_if_secrets_empty` — they are optional by design.

- [ ] **Step 3: Verify settings loads without error**

```powershell
.venv\Scripts\python.exe -c "from app.core.settings import settings; print(settings.N8N_WEBHOOK_URL, settings.N8N_WEBHOOK_SECRET)"
```

Expected: two empty strings printed, no exception.

- [ ] **Step 4: Commit**

```powershell
git add app/core/settings.py requirements.txt
git commit -m "feat: add N8N_WEBHOOK_URL and N8N_WEBHOOK_SECRET settings; add respx"
```

---

## Task 2: `_notify_n8n` function + unit tests

**Files:**
- Create: `tests/unit/test_n8n_notify.py`
- Modify: `app/post_call_analysis/worker.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_n8n_notify.py`:

```python
import pytest
import httpx
import respx
from httpx import Response
from unittest.mock import patch

from app.post_call_analysis.worker import _notify_n8n

WEBHOOK_URL = "http://n8n:5678/webhook/post-call"

SAMPLE_PAYLOAD = {
    "call_id": "00000000-0000-0000-0000-000000000001",
    "lead_id": "00000000-0000-0000-0000-000000000002",
    "phone_number": "+919876543210",
    "first_name": "Ravi",
    "last_name": "Sharma",
    "company": "ABC Corp",
    "call_outcome": "callback_requested",
    "callback_requested": True,
    "callback_time": "2026-05-10T10:00:00+05:30",
    "summary": "Lead asked for callback.",
    "lead_temperature": "hot",
    "sentiment": "positive",
    "objections_raised": ["too busy"],
    "next_action": "Schedule callback.",
}


@pytest.mark.asyncio
async def test_notify_sends_correct_url_and_secret():
    with respx.mock() as m:
        route = m.post(WEBHOOK_URL).mock(return_value=Response(200))
        with patch("app.post_call_analysis.worker.settings") as s:
            s.N8N_WEBHOOK_URL = WEBHOOK_URL
            s.N8N_WEBHOOK_SECRET = "test-secret"
            await _notify_n8n(SAMPLE_PAYLOAD)
    assert route.called
    assert route.calls[0].request.headers["X-Internal-Webhook-Secret"] == "test-secret"


@pytest.mark.asyncio
async def test_notify_skips_when_url_empty():
    with respx.mock() as m:
        # no routes registered — any HTTP call would raise
        with patch("app.post_call_analysis.worker.settings") as s:
            s.N8N_WEBHOOK_URL = ""
            s.N8N_WEBHOOK_SECRET = ""
            await _notify_n8n(SAMPLE_PAYLOAD)  # must not raise, must not call HTTP


@pytest.mark.asyncio
async def test_notify_swallows_connect_error():
    with respx.mock() as m:
        m.post(WEBHOOK_URL).mock(side_effect=httpx.ConnectError("refused"))
        with patch("app.post_call_analysis.worker.settings") as s:
            s.N8N_WEBHOOK_URL = WEBHOOK_URL
            s.N8N_WEBHOOK_SECRET = "secret"
            await _notify_n8n(SAMPLE_PAYLOAD)  # must not raise


@pytest.mark.asyncio
async def test_notify_swallows_read_timeout():
    with respx.mock() as m:
        m.post(WEBHOOK_URL).mock(side_effect=httpx.ReadTimeout("timed out"))
        with patch("app.post_call_analysis.worker.settings") as s:
            s.N8N_WEBHOOK_URL = WEBHOOK_URL
            s.N8N_WEBHOOK_SECRET = "secret"
            await _notify_n8n(SAMPLE_PAYLOAD)  # must not raise


@pytest.mark.asyncio
async def test_notify_swallows_http_500():
    with respx.mock() as m:
        m.post(WEBHOOK_URL).mock(return_value=Response(500))
        with patch("app.post_call_analysis.worker.settings") as s:
            s.N8N_WEBHOOK_URL = WEBHOOK_URL
            s.N8N_WEBHOOK_SECRET = "secret"
            await _notify_n8n(SAMPLE_PAYLOAD)  # 500 is not an exception; must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_n8n_notify.py -v
```

Expected: 5 errors — `ImportError: cannot import name '_notify_n8n' from 'app.post_call_analysis.worker'`

- [ ] **Step 3: Add `_notify_n8n` to `app/post_call_analysis/worker.py`**

Add `import httpx` to the imports at the top of the file (after the existing `import anthropic` line):

```python
import httpx
```

Then add this function after the existing `_write_failure_flag` function (before `_run_analysis`):

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

- [ ] **Step 4: Run tests to verify they pass**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_n8n_notify.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```powershell
git add tests/unit/test_n8n_notify.py app/post_call_analysis/worker.py
git commit -m "feat: add _notify_n8n fire-and-forget webhook notifier"
```

---

## Task 3: Wire `_notify_n8n` into `_run_analysis`

**Files:**
- Create: `tests/unit/test_worker_notify.py`
- Modify: `app/post_call_analysis/worker.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_worker_notify.py`:

```python
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.post_call_analysis.worker import _run_analysis
from app.post_call_analysis.schemas import ExtractionResult

CALLBACK_EXTRACTION = ExtractionResult(
    call_outcome="callback_requested",
    callback_time="2026-05-10T10:00:00+05:30",
    objections_raised=["too busy"],
    next_action="Schedule a callback for tomorrow morning.",
    summary="Lead asked for a callback.",
    sentiment_reason="Positive tone throughout.",
    lead_temperature="hot",
    sentiment="positive",
    dnc_requested=False,
)


def _make_factory():
    call_id = uuid.uuid4()

    transcript = MagicMock()
    transcript.call_id = call_id
    transcript.raw_transcript = "Agent: Hi. User: Please call me back."

    call_obj = MagicMock()
    call_obj.id = call_id
    call_obj.lead_id = uuid.uuid4()

    lead = MagicMock()
    lead.id = call_obj.lead_id
    lead.phone_number = "+919876543210"
    lead.first_name = "Ravi"
    lead.last_name = "Sharma"
    lead.company = "ABC Corp"

    read_session = AsyncMock()
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = transcript
    r2 = MagicMock(); r2.scalar_one_or_none.return_value = call_obj
    r3 = MagicMock(); r3.scalar_one_or_none.return_value = lead
    read_session.execute = AsyncMock(side_effect=[r1, r2, r3])
    read_cm = AsyncMock()
    read_cm.__aenter__ = AsyncMock(return_value=read_session)
    read_cm.__aexit__ = AsyncMock(return_value=False)

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
    return factory, transcript.call_id


@pytest.mark.asyncio
async def test_run_analysis_calls_notify_after_db_writes():
    factory, call_id = _make_factory()
    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude", return_value=CALLBACK_EXTRACTION):
            with patch("app.post_call_analysis.worker.scan", return_value=False):
                with patch("app.post_call_analysis.worker._notify_n8n", new_callable=AsyncMock) as mock_notify:
                    await _run_analysis(str(call_id))
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_payload_contains_required_keys():
    factory, call_id = _make_factory()
    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude", return_value=CALLBACK_EXTRACTION):
            with patch("app.post_call_analysis.worker.scan", return_value=False):
                with patch("app.post_call_analysis.worker._notify_n8n", new_callable=AsyncMock) as mock_notify:
                    await _run_analysis(str(call_id))
    payload = mock_notify.call_args[0][0]
    required = (
        "call_id", "lead_id", "phone_number", "first_name", "last_name",
        "company", "call_outcome", "callback_requested", "callback_time",
        "summary", "lead_temperature", "sentiment", "objections_raised", "next_action",
    )
    for key in required:
        assert key in payload, f"Missing key in n8n payload: {key}"
    assert payload["callback_requested"] is True
    assert payload["call_outcome"] == "callback_requested"


@pytest.mark.asyncio
async def test_notify_not_called_when_transcript_missing():
    call_id = uuid.uuid4()
    read_session = AsyncMock()
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = None
    read_session.execute = AsyncMock(return_value=r1)
    read_cm = AsyncMock()
    read_cm.__aenter__ = AsyncMock(return_value=read_session)
    read_cm.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=read_cm)

    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._notify_n8n", new_callable=AsyncMock) as mock_notify:
            await _run_analysis(str(call_id))
    mock_notify.assert_not_awaited()
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_worker_notify.py -v
```

Expected: `test_run_analysis_calls_notify_after_db_writes` FAILS — `_notify_n8n` never called (not yet wired).

- [ ] **Step 3: Modify `_run_analysis` — capture extra lead fields**

In `app/post_call_analysis/worker.py`, inside `_run_analysis`, add three new variable declarations alongside the existing `lead_phone` and `lead_id` declarations (around line 99):

```python
        lead_phone: str | None = None
        lead_id: uuid.UUID | None = None
        lead_first_name: str | None = None
        lead_last_name: str | None = None
        lead_company: str | None = None
```

Then extend the `if lead is not None:` block to also capture the new fields:

```python
            if lead is not None:
                lead_phone = lead.phone_number
                lead_id = lead.id
                lead_first_name = lead.first_name
                lead_last_name = lead.last_name
                lead_company = lead.company
```

- [ ] **Step 4: Modify `_run_analysis` — call `_notify_n8n` at the end**

At the very end of `_run_analysis`, after the existing `logger.info(...)` call, add:

```python
    await _notify_n8n({
        "call_id": str(call_id),
        "lead_id": str(lead_id) if lead_id else None,
        "phone_number": lead_phone,
        "first_name": lead_first_name,
        "last_name": lead_last_name,
        "company": lead_company,
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

- [ ] **Step 5: Run new tests and existing worker tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_worker_notify.py tests/unit/test_post_call_worker.py -v
```

Expected: `8 passed` (3 new + 5 existing; the existing tests mock `_notify_n8n` implicitly via the module-level patch — but actually they don't, so they'll call the real `_notify_n8n` which will skip because `N8N_WEBHOOK_URL` is empty by default). All 8 should pass.

- [ ] **Step 6: Commit**

```powershell
git add tests/unit/test_worker_notify.py app/post_call_analysis/worker.py
git commit -m "feat: wire _notify_n8n into _run_analysis after DB writes"
```

---

## Task 4: Docker Compose — add n8n service

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add the n8n service and update existing services**

Replace the entire `docker-compose.yml` with:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: agent
      POSTGRES_DB: agent_ops
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://agent:agent@db:5432/agent_ops
      REDIS_URL: redis://redis:6379/0
      N8N_WEBHOOK_URL: http://n8n:5678/webhook/post-call
      N8N_WEBHOOK_SECRET: changeme
    depends_on:
      - db
      - redis

  dashboard:
    build:
      context: app/dashboard
      dockerfile: Dockerfile.dashboard
    ports:
      - "3000:3000"
    environment:
      API_INTERNAL_URL: http://api:8000
      NEXT_PUBLIC_WS_URL: ws://localhost:8000
    depends_on:
      - api

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

volumes:
  pgdata:
  n8n_data:
```

- [ ] **Step 2: Verify YAML is valid**

```powershell
docker compose config --quiet
```

Expected: no errors, silent output.

- [ ] **Step 3: Commit**

```powershell
git add docker-compose.yml
git commit -m "feat: add n8n service to Docker Compose with n8n_data volume"
```

---

## Task 5: n8n flow JSON + README

**Files:**
- Create: `n8n-flows/post-call-automation.json`
- Create: `n8n-flows/README.md`

- [ ] **Step 1: Create the `n8n-flows/` directory and flow JSON**

Create `n8n-flows/post-call-automation.json` with this exact content:

```json
{
  "name": "Post-Call Automation",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "post-call",
        "responseMode": "onReceived",
        "options": {}
      },
      "id": "a1b2c3d4-0001-0001-0001-000000000001",
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1,
      "position": [240, 300],
      "webhookId": "post-call-automation"
    },
    {
      "parameters": {
        "operation": "append",
        "documentId": {
          "__rl": true,
          "value": "={{ $env.GOOGLE_SHEET_ID }}",
          "mode": "id"
        },
        "sheetName": {
          "__rl": true,
          "value": "Sheet1",
          "mode": "name"
        },
        "columns": {
          "mappingMode": "defineBelow",
          "value": {
            "call_id": "={{ $json.call_id }}",
            "phone_number": "={{ $json.phone_number }}",
            "first_name": "={{ $json.first_name }}",
            "last_name": "={{ $json.last_name }}",
            "company": "={{ $json.company }}",
            "call_outcome": "={{ $json.call_outcome }}",
            "lead_temperature": "={{ $json.lead_temperature }}",
            "sentiment": "={{ $json.sentiment }}",
            "summary": "={{ $json.summary }}",
            "callback_time": "={{ $json.callback_time }}",
            "logged_at": "={{ new Date().toISOString() }}"
          }
        },
        "options": {
          "valueInputMode": "USER_ENTERED"
        }
      },
      "id": "a1b2c3d4-0002-0002-0002-000000000002",
      "name": "Log to Sheets",
      "type": "n8n-nodes-base.googleSheets",
      "typeVersion": 4,
      "position": [460, 300],
      "credentials": {
        "googleSheetsOAuth2Api": {
          "id": "REPLACE_WITH_CREDENTIAL_ID",
          "name": "Google Sheets account"
        }
      }
    },
    {
      "parameters": {
        "conditions": {
          "options": {
            "caseSensitive": true,
            "leftValue": "",
            "typeValidation": "strict"
          },
          "conditions": [
            {
              "id": "sms-cond-1",
              "leftValue": "={{ $json.call_outcome }}",
              "rightValue": "interested",
              "operator": {
                "type": "string",
                "operation": "equals"
              }
            },
            {
              "id": "sms-cond-2",
              "leftValue": "={{ $json.call_outcome }}",
              "rightValue": "callback_requested",
              "operator": {
                "type": "string",
                "operation": "equals"
              }
            }
          ],
          "combinator": "any"
        },
        "options": {}
      },
      "id": "a1b2c3d4-0003-0003-0003-000000000003",
      "name": "Should SMS?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [680, 180]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://api.telnyx.com/v2/messages",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "Authorization",
              "value": "=Bearer {{ $env.TELNYX_API_KEY }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={\n  \"from\": \"{{ $env.TELNYX_FROM_NUMBER }}\",\n  \"to\": \"{{ $json.phone_number }}\",\n  \"text\": \"Hi {{ $json.first_name }}, thanks for speaking with us today. {{ $json.next_action }}\"\n}",
        "options": {}
      },
      "id": "a1b2c3d4-0004-0004-0004-000000000004",
      "name": "Send SMS",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "position": [900, 80]
    },
    {
      "parameters": {
        "conditions": {
          "options": {
            "caseSensitive": true,
            "leftValue": "",
            "typeValidation": "strict"
          },
          "conditions": [
            {
              "id": "cal-cond-1",
              "leftValue": "={{ $json.callback_requested }}",
              "rightValue": true,
              "operator": {
                "type": "boolean",
                "operation": "true"
              }
            },
            {
              "id": "cal-cond-2",
              "leftValue": "={{ $json.callback_time }}",
              "rightValue": "",
              "operator": {
                "type": "string",
                "operation": "notEmpty"
              }
            }
          ],
          "combinator": "all"
        },
        "options": {}
      },
      "id": "a1b2c3d4-0005-0005-0005-000000000005",
      "name": "Should book?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [680, 420]
    },
    {
      "parameters": {
        "calendar": {
          "__rl": true,
          "value": "={{ $env.GOOGLE_CALENDAR_ID }}",
          "mode": "id"
        },
        "start": "={{ $json.callback_time }}",
        "end": "={{ DateTime.fromISO($json.callback_time).plus({minutes: 30}).toISO() }}",
        "additionalFields": {
          "summary": "=Callback: {{ $json.first_name }} {{ $json.last_name }}",
          "description": "=Company: {{ $json.company }}\n\n{{ $json.summary }}\n\nNext action: {{ $json.next_action }}"
        }
      },
      "id": "a1b2c3d4-0006-0006-0006-000000000006",
      "name": "Create Calendar Event",
      "type": "n8n-nodes-base.googleCalendar",
      "typeVersion": 1,
      "position": [900, 500],
      "credentials": {
        "googleCalendarOAuth2Api": {
          "id": "REPLACE_WITH_CREDENTIAL_ID",
          "name": "Google Calendar account"
        }
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [
        [
          { "node": "Log to Sheets", "type": "main", "index": 0 }
        ]
      ]
    },
    "Log to Sheets": {
      "main": [
        [
          { "node": "Should SMS?", "type": "main", "index": 0 },
          { "node": "Should book?", "type": "main", "index": 0 }
        ]
      ]
    },
    "Should SMS?": {
      "main": [
        [{ "node": "Send SMS", "type": "main", "index": 0 }],
        []
      ]
    },
    "Should book?": {
      "main": [
        [{ "node": "Create Calendar Event", "type": "main", "index": 0 }],
        []
      ]
    }
  },
  "pinData": {},
  "settings": {
    "executionOrder": "v1"
  },
  "staticData": null,
  "tags": [],
  "meta": {
    "templateCredsSetupCompleted": false,
    "instanceId": "voice-outbound-agent"
  },
  "id": "post-call-automation-v1",
  "versionId": "2026-05-09"
}
```

- [ ] **Step 2: Create `n8n-flows/README.md`**

```markdown
# n8n Flows — Post-Call Automation

## What this flow does

After every call is analysed by the RQ worker, a webhook fires to n8n which:

1. **Always** — appends one row to a Google Sheet (call_id, outcome, sentiment, summary, etc.)
2. **If `call_outcome` is `interested` or `callback_requested`** — sends a Telnyx SMS to the lead
3. **If `callback_requested == true` and `callback_time` is set** — creates a 30-min Google Calendar event at `callback_time`

---

## Setup

### 1. Start n8n

```bash
docker compose up n8n
```

Open http://localhost:5678 and log in (admin / admin).

### 2. Import the flow

Workflows → **Import from file** → select `n8n-flows/post-call-automation.json`

### 3. Create credentials (n8n UI → Credentials)

| Credential type | Used by node |
|---|---|
| Google Sheets OAuth2 | Log to Sheets |
| Google Calendar OAuth2 | Create Calendar Event |

After creating each credential, open the relevant node, select the credential from the dropdown, and save. The placeholder `REPLACE_WITH_CREDENTIAL_ID` values in the JSON will be overwritten by n8n when you select the credential.

### 4. Set n8n environment variables

In the n8n container (or `docker-compose.yml` → `n8n.environment`):

```
TELNYX_API_KEY=your_telnyx_api_key
TELNYX_FROM_NUMBER=+91XXXXXXXXXX
GOOGLE_SHEET_ID=your_google_spreadsheet_id
GOOGLE_CALENDAR_ID=primary
```

The spreadsheet must have a sheet named `Sheet1` with these column headers in row 1:
`call_id | phone_number | first_name | last_name | company | call_outcome | lead_temperature | sentiment | summary | callback_time | logged_at`

### 5. Activate the flow

Toggle the flow to **Active** in the n8n UI.

---

## Test with curl

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

Expected result:
- Google Sheet gains a new row
- Telnyx sends an SMS to +919876543210
- Google Calendar creates a 30-min event at 2026-05-10T10:00:00+05:30

---

## Security note

The `X-Internal-Webhook-Secret` header is checked by the n8n flow using the **Header Auth** method. Set the same secret in:
- `api` service env: `N8N_WEBHOOK_SECRET=changeme`
- n8n flow Webhook node → Header Auth credential: value `changeme`

Change `changeme` to a strong random value in production.
```

- [ ] **Step 3: Verify JSON is valid**

```powershell
.venv\Scripts\python.exe -c "import json; json.load(open('n8n-flows/post-call-automation.json')); print('JSON valid')"
```

Expected: `JSON valid`

- [ ] **Step 4: Commit**

```powershell
git add n8n-flows/
git commit -m "feat: add n8n post-call automation flow and setup README"
```

---

## Task 6: Final test run

**Files:** none

- [ ] **Step 1: Run the full unit test suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/ -q --tb=short
```

Expected: `225 passed, 1 failed` — the 1 failure is the pre-existing `test_vad_silero_wrapper.py::TestSileroWrapper::test_infer_returns_float_in_valid_range` (numpy not installed). All new tests pass.

- [ ] **Step 2: If any new failures, fix them and commit**

If tests other than `test_infer_returns_float_in_valid_range` fail, fix the root cause. Do not suppress failures with `pytest.mark.skip`.

- [ ] **Step 3: Commit final state**

```powershell
git add -A
git commit -m "test: verify 225 unit tests pass for Module 8 n8n-flows"
```

---

## Acceptance Criteria

- [ ] `pytest tests/unit/ -q` → 225 passed, 1 pre-existing skip
- [ ] `_notify_n8n` is unreachable via network when `N8N_WEBHOOK_URL = ""`
- [ ] `_notify_n8n` never raises — all HTTP failures are caught and logged
- [ ] `_run_analysis` calls `_notify_n8n` after both DB writes complete
- [ ] `docker compose config` validates without errors
- [ ] `python -c "import json; json.load(open('n8n-flows/post-call-automation.json'))"` succeeds
