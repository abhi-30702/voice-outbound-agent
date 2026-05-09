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
