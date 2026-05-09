# Next Session - Quick Start Guide

## Current Status (as of 2026-05-09 EOD)

✅ **Module 1 (db-schema)**: Complete and merged to master
✅ **Module 2 (dialing-worker)**: Complete and merged to master
✅ **Module 3 (webhook-receiver)**: Complete and merged to master
✅ **Module 4 (post-call-analysis)**: Complete and merged to master
✅ **Module 5 (vad-pipeline)**: Complete and merged to master
✅ **Module 6 (conversation-prompts)**: Complete and merged to master
🔁 **Module 7 (dashboard)**: COMPLETE — PR open, pending merge
⏳ **Module 8 (n8n-flows)**: NEXT — not started

## Git State

**Active branch:** feature/module-7-dashboard (15 commits ahead of master)
**PR:** https://github.com/abhi-30702/voice-outbound-agent/pull/new/feature/module-7-dashboard
**master:** clean at f0451db
**Test status:** 215 unit tests passing (1 pre-existing numpy skip in test_vad_silero_wrapper)

## First Action Next Session

**Step 1 — Merge the Module 7 PR.**
If not yet merged, either merge via GitHub UI or run:
```powershell
git checkout master
git pull
git merge feature/module-7-dashboard
git push
git branch -d feature/module-7-dashboard
```

**Step 2 — Start Module 8 (n8n-flows).**
Create a new feature branch and invoke the brainstorming skill.

## What Was Built in Module 7 (dashboard)

**Backend — `app/dashboard_api/`:**
- `schemas.py` — 8 Pydantic v2 models (CampaignOut, CampaignCreate, CampaignStatusPatch, LeadOut, LeadUploadResult, LeadAssign, ActiveCall, KpiOut)
- `websocket.py` — ConnectionManager (connect/disconnect/broadcast), module-level `broadcast()` coroutine imported by webhook handlers
- `kpi.py` — `get_kpi(db, range_)` → KpiOut; supports today / 7d / 30d ranges
- `campaigns.py` — list_campaigns (outerjoin for lead count), create_campaign, patch_campaign_status
- `leads.py` — list_leads, upload_leads (CSV parse via csv.DictReader), assign_leads; parse_csv validates required columns {phone_number, timezone}
- `router.py` — api_router (/api prefix) + ws_router; all ValueError → HTTPException (400/404/422)

**Webhook integration:**
- `app/webhook_receiver/handlers/call_started.py` — broadcasts `call_started` event after DB write
- `app/webhook_receiver/handlers/transcript_updated.py` — broadcasts `transcript_updated` event
- `app/webhook_receiver/handlers/call_ended.py` — broadcasts `call_ended` event
- `app/webhook_receiver/main.py` — mounts api_router and ws_router

**Frontend — `app/dashboard/` (Next.js 14 App Router):**
- `/` → LiveCallFeed (WebSocket) + CallCard list
- `/campaigns` → CampaignTable (PATCH actions) + CreateCampaignModal + LeadUpload
- `/kpi` → KpiChart (Recharts AreaChart, SWR 30s polling) + RangeSelector
- Styling: Tailwind CSS only

**Docker:**
- `app/dashboard/Dockerfile.dashboard` — 3-stage node:20-alpine (deps → builder → runner), output: standalone
- `docker-compose.yml` — dashboard service on port 3000; API_INTERNAL_URL=http://api:8000 (server-side), NEXT_PUBLIC_WS_URL=ws://localhost:8000 (browser)

**Tests (31 new, 215 total):**
- `tests/unit/test_dashboard_schemas.py` — 7 tests
- `tests/unit/test_dashboard_websocket.py` — 6 tests
- `tests/unit/test_dashboard_kpi.py` — 5 tests
- `tests/unit/test_dashboard_campaigns.py` — 5 tests
- `tests/unit/test_dashboard_leads.py` — 9 tests

**Known minor issues (non-blocking):**
- `PATCH /campaigns/{id}/status` always returns `lead_count=0` (frontend ignores it)
- `GET /api/calls/active` does not include `phone_number` (CallCard falls back to call_id display)

## Module 8 (n8n-flows) — What to Build

Per PRD.md §4, Module 9 (our Phase 8): post-call automation flows in n8n.

Key flows to design:
- CRM push (update contact record after call ends)
- SMS follow-up (send confirmation SMS via Telnyx)
- Calendar booking (book a slot after successful qualification)

Target directory: `n8n-flows/` (exported n8n JSON files)
Entry point: n8n webhook trigger on call_ended event from webhook receiver

**Start the session with:**
1. Read PRD.md §4 module table and any n8n-related sections
2. Invoke brainstorming skill to design the flows
3. Then writing-plans skill for the implementation plan
4. Then subagent-driven-development to execute

## Test Commands

Fast tests (no model load, ~3s):
```powershell
.venv\Scripts\python.exe -m pytest tests/unit/ --ignore=tests/unit/test_vad_silero_wrapper.py -q
```

All tests including slow Silero model tests:
```powershell
.venv\Scripts\python.exe -m pytest tests/unit/ -q
```

TypeScript check:
```powershell
cd app\dashboard; npx tsc --noEmit
```

## GitHub

- Repo: https://github.com/abhi-30702/voice-outbound-agent
- gh CLI now installed (run `gh auth login` to authenticate)
