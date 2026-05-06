# ==============================================================================
# voice-outbound-agent-sessions.ps1
# Session launcher for voice-outbound-agent.
# Owner: Srinivas / Fidelitus Corp + SherpaVector
# Usage: .\voice-outbound-agent-sessions.ps1 -Session <name>
# ==============================================================================

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet(
        "audit",
        "db-schema",
        "dialing-worker",
        "retell-integration",
        "webhook-receiver",
        "post-call-analysis",
        "vad-pipeline",
        "conversation-prompts",
        "dashboard",
        "n8n-flows",
        "docker-compose",
        "evals",
        "debug",
        "list"
    )]
    [string]$Session
)

$PROJECT_ROOT = "D:\staging\voice-outbound-agent"
$HAIKU        = "claude-haiku-4-5-20251001"
$SONNET       = "claude-sonnet-4-6"

$sessions = @{

    # ── Phase 0: Audit ──────────────────────────────────────────────────────────
    audit = @{
        model = $SONNET
        task  = "TASK-000"
        label = "Session 0 · Audit — Read Only"
        prompt = @'
Stack: Python 3.13, FastAPI, PostgreSQL 16, Redis, Retell AI, Telnyx, ElevenLabs, Silero VAD, Claude Sonnet, Docker, Next.js 14
PRD: PRD.md (read it now — all sections)
Task file: tasks/TASK-000-repo-init.md
Module scope: ENTIRE repository — read all files. NO code changes.

Your job this session:
1. Read PRD.md completely
2. Read all existing files in the project
3. Report: what exists, what is missing, what needs to be built first
4. Produce a prioritised checklist for Phase 1 (db-schema)
5. Flag any dependency conflicts or env variable gaps

PDCA: present findings only. No writing code. No editing files.
Output format: structured checklist the developer can approve.
'@
    }

    # ── Phase 1: DB Schema ────────────────────────────────────────────────────
    "db-schema" = @{
        model = $HAIKU
        task  = "TASK-001"
        label = "Session 1 · DB Schema + Migrations"
        prompt = @'
Stack: Python 3.13, SQLAlchemy 2.x, Alembic, PostgreSQL 16, psycopg2-binary
PRD: PRD.md Section 5 (Database Schema) — read this first
Task file: tasks/TASK-001-db-schema.md
Module scope: app/db-schema/ ONLY

Build:
1. SQLAlchemy models for: campaigns, leads, dnc_registry, call_logs, call_transcripts
   — all in schema agent_operations
   — JSONB columns: prompt_template, llm_config, structured_data, custom_vars
2. Alembic env.py + initial migration script
3. SQL grant script: memories_role with SELECT/INSERT/UPDATE only (no DROP/DELETE)
4. Seed script: one test campaign, two leads (one in DNC, one clean)
5. Connection test: pytest tests/test_db_connection.py

Context7: use for SQLAlchemy 2.x API and Alembic docs.
PDCA: present schema plan first. Wait for approval. Then write code.
Key rule: parameterised queries only — no f-strings in SQL.
'@
    }

    # ── Phase 2: Dialing Worker ───────────────────────────────────────────────
    "dialing-worker" = @{
        model = $SONNET
        task  = "TASK-002"
        label = "Session 2 · Dialing Worker (RQ + 1CPS)"
        prompt = @'
Stack: Python 3.13, FastAPI, asyncio, Redis, RQ, pytz
PRD: PRD.md Section 8 (Dialing Worker Logic) — read this first
Task file: tasks/TASK-002-dialing-worker.md
Module scope: app/dialing-worker/ ONLY

Build:
1. Async worker that polls agent_operations.leads for pending records
2. DNC check via SQL NOT EXISTS (never application-level filtering)
3. Timezone gate: only dial between 08:00–21:00 lead local time (use pytz)
4. Strict 1 CPS enforced via asyncio.sleep(1.0) — no exceptions
5. Update lead.status: pending → calling on dispatch
6. Exponential backoff on HTTP 429 and SIP 503 errors
7. Batch size: 50 leads per poll cycle; poll interval: 5 seconds
8. Unit tests: test_dnc_check, test_timezone_gate, test_rate_limit

Context7: use for RQ (Redis Queue) and pytz APIs.
PDCA: present the worker pseudocode from PRD.md as starting point. Get approval. Then implement.
Key rule: the DNC SQL check is a NOT EXISTS subquery in the SELECT — hardcode this pattern.
'@
    }

    # ── Phase 3: Retell Integration ───────────────────────────────────────────
    "retell-integration" = @{
        model = $SONNET
        task  = "TASK-003"
        label = "Session 3 · Retell AI API Client"
        prompt = @'
Stack: Python 3.13, httpx, Retell AI REST API v2, Telnyx SIP
PRD: PRD.md Sections 3 (Architecture) and 6 (Dialing Engine) — read these first
Task file: tasks/TASK-003-retell-integration.md
Module scope: app/retell-integration/ ONLY

Build:
1. Retell AI async API client (create_call, get_call, list_calls)
2. Agent configuration: GPT-4o Realtime model, ElevenLabs voice, Deepgram STT
3. Dynamic variables injection from leads.custom_vars + first_name + company
4. Telnyx SIP trunk config: E.164 format validation, CNAM rotation pool
5. call_metadata mapper: PRD Section 9 structured output schema pre-loaded
6. Integration test: create a test call to a Telnyx test number (not live)

Context7: use for Retell AI API and httpx docs.
PDCA: show API call structure from PRD Section 8 (pseudocode) for approval first.
Key rule: all destination numbers must be validated as E.164 before dispatch.
'@
    }

    # ── Phase 4: Webhook Receiver ─────────────────────────────────────────────
    "webhook-receiver" = @{
        model = $SONNET
        task  = "TASK-004"
        label = "Session 4 · FastAPI Webhook Receiver"
        prompt = @'
Stack: Python 3.13, FastAPI, SQLAlchemy, hmac, hashlib
PRD: PRD.md Section 9 (Webhook Events) — read this first
Task file: tasks/TASK-004-webhook-receiver.md
Module scope: app/webhook-receiver/ ONLY

Build:
1. FastAPI app with 4 endpoints:
   POST /webhooks/call-started   → update lead.status = "calling", insert call_log
   POST /webhooks/transcript     → broadcast to WebSocket (dashboard)
   POST /webhooks/call-ended     → update call_log duration + disconnect_reason + recording_url
   POST /webhooks/call-analyzed  → dispatch to post-call-analysis module
2. x-retell-signature HMAC verification on ALL endpoints (reject if invalid — 401)
3. WebSocket endpoint: /ws/calls — broadcast transcript_updated events
4. Error handling: log + 200 OK on known events; 400 on unknown; never 500 to Retell
5. Tests: test_signature_verification (valid + tampered), test_all_four_endpoints

Context7: use for FastAPI WebSocket and HMAC docs.
PDCA: show endpoint + security design for approval first.
Key rule: ALWAYS return HTTP 200 to Retell even on internal errors — log the error, never let Retell retry storm.
'@
    }

    # ── Phase 5: Post-Call Analysis ───────────────────────────────────────────
    "post-call-analysis" = @{
        model = $SONNET
        task  = "TASK-005"
        label = "Session 5 · Post-Call Claude Sonnet Extraction"
        prompt = @'
Stack: Python 3.13, Anthropic Python SDK, SQLAlchemy, JSONB
PRD: PRD.md Section 10 (Structured Output Schema) — read this first
Task file: tasks/TASK-005-post-call-analysis.md
Module scope: app/post-call-analysis/ ONLY

Build:
1. Async function: analyze_transcript(call_id, raw_transcript) → structured_data dict
2. Claude Sonnet prompt: extract PRD Section 10 JSON schema from transcript
3. Schema: intent_confirmed, interest_level, callback_requested, callback_time,
   objections_raised, key_facts_captured, sentiment, call_outcome, summary
4. Write structured_data to call_transcripts.structured_data (JSONB)
5. If call_outcome == "dnc_request" → auto-insert phone_number into dnc_registry
6. If callback_requested == true → store callback_time; n8n picks this up
7. Tests: test with 3 sample transcripts (qualified / unqualified / dnc_request)

Context7: use for Anthropic Python SDK docs.
PDCA: show the prompt template for Claude Sonnet extraction for approval first.
Key rule: use structured_outputs / JSON mode — never parse free-form text.
'@
    }

    # ── Phase 6: VAD Pipeline ─────────────────────────────────────────────────
    "vad-pipeline" = @{
        model = $SONNET
        task  = "TASK-006"
        label = "Session 6 · Silero VAD State Machine"
        prompt = @'
Stack: Python 3.13, silero-vad (PyTorch), numpy, asyncio
PRD: PRD.md Section 6 (VAD State Machine) — read this first
Task file: tasks/TASK-006-vad-pipeline.md
Module scope: app/vad-pipeline/ ONLY

Build:
1. Silero VAD wrapper class: stream 16kHz PCM audio chunks
2. State machine: QUIET → STARTING (200ms sustained) → SPEAKING → STOPPING (800ms silence)
3. Callbacks: on_speech_start, on_speech_end, on_interrupt
4. on_interrupt: emit HALT signal + context truncation offset (word count spoken)
5. Configurable thresholds via env vars: VAD_ONSET_MS, VAD_OFFSET_MS
6. Async audio chunk queue feeding the state machine
7. Tests: test with synthetic audio (300ms speech, 900ms silence, interrupt scenario)

Context7: use for silero-vad and PyTorch Audio docs.
PDCA: draw the state machine diagram (ASCII) for approval before coding.
Key rule: interrupts must emit HALT within one audio chunk (max 20ms) — no batching.
'@
    }

    # ── Phase 7: Conversation Prompts ─────────────────────────────────────────
    "conversation-prompts" = @{
        model = $SONNET
        task  = "TASK-007"
        label = "Session 7 · Conversation Prompt Library"
        prompt = @'
Stack: Python 3.13, Jinja2 (templating), JSONB
PRD: PRD.md Section 7 (Conversation Prompt Design) — read this first
Task file: tasks/TASK-007-conversation-prompts.md
Module scope: app/conversation-prompts/ ONLY

Build:
3 persona templates stored as JSONB in campaigns.prompt_template:
  1. lead-qualification: verify decision-maker + budget + timeline
  2. appointment-confirm: confirm date/time + send calendar link
  3. feedback-collection: NPS + one open question

Each template must:
- Pass the prompt-review skill (max 12 words per sentence, no bullets, phonetic acronyms)
- Include: PERSONA, OBJECTIVE, FLOW (steps with wait instructions), OBJECTIONS, ESCAPE HATCH
- Dynamic variable slots: {{first_name}}, {{company}}, {{agent_name}}

Build: Jinja2 renderer that takes template + lead vars → final system prompt string
Build: prompt_review validator function (runs the SKILLS.md prompt-review checks)
Tests: render all 3 templates with mock data; validate pass/fail

PDCA: show persona + flow for template 1 for approval first.
Key rule: never use asterisks, hashes, pipes, or bullet points in any TTS-bound text.
'@
    }

    # ── Phase 8: Dashboard ────────────────────────────────────────────────────
    dashboard = @{
        model = $SONNET
        task  = "TASK-008"
        label = "Session 8 · Next.js Live Dashboard"
        prompt = @'
Stack: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Recharts, WebSocket
PRD: PRD.md Section 11 (KPIs) — read this first
Task file: tasks/TASK-008-dashboard.md
Module scope: app/dashboard/ ONLY

Build:
1. Campaign Manager page: list campaigns, status badge, lead count, create/pause
2. Live Calls page: WebSocket feed of active calls + live transcript overlay
3. KPI Dashboard: charts for avg call duration, detection rate, structured output completion, abandon rate
4. Lead Import page: CSV upload → validate E.164 → insert into leads table
5. DNC Manager page: view dnc_registry, add/remove entries

API calls: FastAPI backend at NEXT_PUBLIC_API_URL
WebSocket: ws://backend/ws/calls

Context7: use for Next.js 14 App Router, shadcn/ui, Recharts docs.
PDCA: show wireframe (text-based) for approval before building.
Key rule: no server-side API keys in client components — all calls via /api/ routes.
'@
    }

    # ── Phase 9: n8n Flows ────────────────────────────────────────────────────
    "n8n-flows" = @{
        model = $HAIKU
        task  = "TASK-009"
        label = "Session 9 · n8n Post-Call Automation"
        prompt = @'
Stack: n8n (self-hosted), PostgreSQL webhook trigger, HTTP Request nodes
PRD: PRD.md Section 3 (Architecture — n8n) — read the automation section
Task file: tasks/TASK-009-n8n-flows.md
Module scope: n8n-flows/ ONLY

Build (as exported n8n JSON workflows):
1. post-call-qualified.json
   Trigger: new row in call_transcripts WHERE call_outcome = "qualified"
   Actions: POST to CRM webhook → send SMS via Telnyx → log to Slack
2. callback-scheduled.json
   Trigger: call_transcripts WHERE callback_requested = true
   Actions: create Google Calendar event at callback_time → SMS confirmation
3. dnc-auto-block.json
   Trigger: new row in dnc_registry
   Actions: log to Slack → optionally sync to external DNC API

Export each as n8n JSON to n8n-flows/<name>.json
Include README with import instructions.

PDCA: describe each flow trigger → action chain for approval first.
'@
    }

    # ── Phase 10: Docker Compose ──────────────────────────────────────────────
    "docker-compose" = @{
        model = $HAIKU
        task  = "TASK-010"
        label = "Session 10 · Docker Compose Full Stack"
        prompt = @'
Stack: Docker Compose, Python 3.13-slim, Node 20-slim, PostgreSQL 16, Redis 7, n8n
PRD: PRD.md Section 13 (Folder Structure) — read this first
Task file: tasks/TASK-010-docker-compose.md
Module scope: docker-compose.yml + Dockerfile per service (project root)

Services to define:
  postgres     postgres:16-alpine; volume for data; healthcheck
  redis        redis:7-alpine; healthcheck
  api          FastAPI app; depends_on postgres + redis
  worker       RQ dialing worker; depends_on postgres + redis
  dashboard    Next.js; depends_on api
  n8n          n8nio/n8n; depends_on postgres

Each service: env_file .env, restart unless-stopped, named volumes.
Add Makefile: make up / make down / make logs / make migrate / make test

PDCA: show service dependency graph for approval first.
Key rule: never hardcode credentials — all from .env file.
'@
    }

    # ── Phase 11: Evals ───────────────────────────────────────────────────────
    evals = @{
        model = $SONNET
        task  = "TASK-011"
        label = "Session 11 · Evals + Load Tests"
        prompt = @'
Stack: Python 3.13, pytest, pytest-asyncio, locust (load testing), mock
PRD: PRD.md Section 12 (Compliance) + Section 11 (KPIs) — read these first
Task file: tasks/TASK-011-evals.md
Module scope: tests/ ONLY

Build:
1. test_dnc_regression.py: insert 100 leads (10 in DNC); verify zero DNC leads are dialed
2. test_worker_rate_limit.py: mock Telnyx; verify worker never exceeds 1 CPS
3. test_timezone_gate.py: leads in 5 timezones; verify only in-hours leads are dialed
4. test_signature_verification.py: tampered webhook → 401; valid → 200
5. test_structured_output.py: 3 transcripts → verify JSON schema compliance
6. locustfile.py: 1000 mock leads → load test; monitor CPS; assert < 1.1 CPS peak
7. KPI check script: kpi_check.py reads call_logs and reports all Section 11 KPIs

PDCA: show test matrix (what is tested + pass criteria) for approval first.
'@
    }

    # ── Debug ──────────────────────────────────────────────────────────────────
    debug = @{
        model = $SONNET
        task  = "TASK-???"
        label = "Debug Session"
        prompt = @'
Stack: Python 3.13, FastAPI, PostgreSQL, Redis, Retell AI
Task: one error, one file, one session.
Paste: (1) full traceback (2) only the function that threw it

Known gotchas:
- DNC check must be SQL NOT EXISTS, not Python filter
- Telnyx rejects non-E.164 numbers silently
- Retell webhook MUST return 200 even on internal errors
- asyncio.sleep(1.0) in worker must not be skipped on retry
- memories_role has no DELETE — use UPDATE status instead
'@
    }
}

# ── List mode ──────────────────────────────────────────────────────────────────
if ($Session -eq "list") {
    Write-Host ""; Write-Host "  voice-outbound-agent · Available Sessions:" -ForegroundColor Cyan; Write-Host ""
    $order = @("audit","db-schema","dialing-worker","retell-integration","webhook-receiver",
               "post-call-analysis","vad-pipeline","conversation-prompts","dashboard",
               "n8n-flows","docker-compose","evals","debug")
    foreach ($key in $order) {
        $s = $sessions[$key]
        $tag = if ($s.model -like "*haiku*") { "Haiku  🟢" } else { "Sonnet 🔵" }
        Write-Host ("  {0,-24} {1,-42} [{2}]" -f $key, $s.label, $tag)
    }
    Write-Host ""; exit 0
}

# ── Session launch ─────────────────────────────────────────────────────────────
$s = $sessions[$Session]
Write-Host ""
Write-Host "  ┌──────────────────────────────────────────────────┐" -ForegroundColor Cyan
Write-Host ("  │  {0,-48}│" -f $s.label) -ForegroundColor Cyan
Write-Host ("  │  Model : {0,-41}│" -f $s.model) -ForegroundColor Cyan
Write-Host ("  │  Task  : {0,-41}│" -f $s.task) -ForegroundColor Cyan
Write-Host "  └──────────────────────────────────────────────────┘" -ForegroundColor Cyan
Write-Host ""
Write-Host $s.prompt -ForegroundColor White
Write-Host ""
$s.prompt | Set-Clipboard
Write-Host "  ✓ Context copied to clipboard." -ForegroundColor Green
Write-Host "  → Paste into Claude Code, then type: superpowers brainstorm" -ForegroundColor Cyan
Write-Host "  → Remember: check context % — /clear at 50%, never /compact" -ForegroundColor Yellow
Write-Host ""
Set-Location $PROJECT_ROOT
$env:ANTHROPIC_MODEL = $s.model
claude --model $s.model
