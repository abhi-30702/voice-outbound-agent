# Next Session - Quick Start Guide

## Current Status (as of 2026-05-09 EOD)

✅ **Module 1 (db-schema)**: Complete and merged to master
✅ **Module 2 (dialing-worker)**: Complete and merged to master
✅ **Module 3 (webhook-receiver)**: Complete and merged to master
✅ **Module 4 (post-call-analysis)**: Complete and merged to master
✅ **Module 5 (vad-pipeline)**: Complete and merged to master
✅ **Module 6 (conversation-prompts)**: Complete and merged to master
🔁 **Module 7 (dashboard)**: COMPLETE — PR open on feature/module-7-dashboard, pending merge
🔧 **Module 8 (n8n-flows)**: IN PROGRESS — Tasks 1-4 done, Tasks 5-6 remaining

## Git State

**Active branch:** feature/module-7-dashboard
**Test status:** 223 unit tests passing (1 pre-existing numpy skip)

Recent commits (Module 8 work so far):
```
9a4b0eb feat: add n8n service to Docker Compose with n8n_data volume  ← Task 4
fbf8d1d feat: wire _notify_n8n into _run_analysis after DB writes        ← Task 3
2ea4382 test: strengthen n8n notify assertions (route.called, no-call guard) ← Task 2 fix
1ba619b feat: add _notify_n8n fire-and-forget webhook notifier            ← Task 2
c8e205d feat: add N8N_WEBHOOK_URL and N8N_WEBHOOK_SECRET settings; add respx ← Task 1
```

## IMMEDIATE ACTION: Resume Module 8 at Task 5

**DO NOT** re-run brainstorming or writing-plans — both are complete.

Invoke `superpowers:subagent-driven-development` and resume at **Task 5**.

### Remaining tasks from `docs/superpowers/plans/2026-05-09-n8n-flows-implementation.md`:

---

#### Task 5: n8n flow JSON + README (NEXT)

Create `n8n-flows/post-call-automation.json` with this EXACT content:

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

Create `n8n-flows/README.md` with this content:

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

After creating each credential, open the relevant node, select the credential from the dropdown, and save.

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

---

## Security note

Change `N8N_WEBHOOK_SECRET: changeme` to a strong random value in production, and set the same value in the n8n Webhook node Header Auth credential.
```

Verify: `python -c "import json; json.load(open('n8n-flows/post-call-automation.json')); print('JSON valid')"`
Commit: `git commit -m "feat: add n8n post-call automation flow and setup README"`

---

#### Task 6: Final test run

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ -q --tb=short`
Expected: 225 passed, 1 pre-existing numpy skip
Commit if fixes needed.

---

## What Was Built in Module 8 (so far)

**`app/core/settings.py`** — Added:
- `N8N_WEBHOOK_URL: str = Field(default="")` — empty = automation disabled
- `N8N_WEBHOOK_SECRET: str = Field(default="")` — X-Internal-Webhook-Secret header value

**`requirements.txt`** — Added `respx==0.21.1` (httpx mock for tests)

**`app/post_call_analysis/worker.py`** — Added:
- `import httpx`
- `_notify_n8n(payload: dict)` — async, fire-and-forget, 5s timeout, catches all exceptions
- In `_run_analysis`: captures `lead_first_name`, `lead_last_name`, `lead_company` from first session
- Calls `await _notify_n8n({14-key payload})` at end of `_run_analysis` after both DB writes

**`tests/unit/test_n8n_notify.py`** — 5 tests for `_notify_n8n` in isolation

**`tests/unit/test_worker_notify.py`** — 3 integration tests (called after writes, payload keys, not called on missing transcript)

**`docker-compose.yml`** — Added n8n service (n8nio/n8n:latest, port 5678, basic auth admin/admin, n8n_data volume, depends_on api). Added N8N_WEBHOOK_URL + N8N_WEBHOOK_SECRET to api service.

## Module 7 PR

Still open at: https://github.com/abhi-30702/voice-outbound-agent/pull/new/feature/module-7-dashboard
Module 8 commits are on the same branch. When both modules are ready, merge the PR to master.

## Test Commands

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/ -q --tb=short
```

## Key Plan/Spec Files

- Plan: `docs/superpowers/plans/2026-05-09-n8n-flows-implementation.md`
- Spec: `docs/superpowers/specs/2026-05-09-n8n-flows-design.md`
