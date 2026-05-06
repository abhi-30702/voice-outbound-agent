# PRD.md — voice-outbound-agent
# Autonomous Outbound Conversational AI Voice Agent with Database-Driven Dialing
# Owner: Srinivas / Fidelitus Corp + SherpaVector
# Location: D:\staging\voice-outbound-agent\PRD.md
# Jai Jagannath

---

## 1. Project Vision

Build a production-grade **autonomous outbound voice AI agent** that:
- Dials leads from a PostgreSQL database
- Conducts fully natural, low-latency conversations (< 500ms response)
- Waits patiently for the human to finish speaking before responding
- Handles interruptions gracefully without derailing conversation state
- Extracts structured data post-call and writes it back to the database
- Enforces DNC/TCPA compliance at the database query level

The experience the product must deliver: _"It waited for me to talk and answered perfectly."_

---

## 2. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| **Orchestration** | Retell AI (managed) | Best-in-class barge-in / turn-taking; ~600ms E2E latency |
| **Live LLM** | GPT-4o Realtime | True multimodal audio; sub-1ms API TTFA |
| **Post-call LLM** | Claude Sonnet (via Anthropic API) | Structured extraction, 200K context, cheaper |
| **TTS** | ElevenLabs v3 | ~75ms TTFA; <20% first-5-second detection rate |
| **STT** | Deepgram Nova-3 (via Retell) | Streaming partial transcripts; open-source fallback: Whisper.cpp |
| **VAD** | Silero VAD (open-source) | 200ms onset / 800ms offset state machine |
| **Telephony / SIP** | Telnyx (primary) | Direct carrier, private edge, lowest network latency |
| **Database** | PostgreSQL 16 | JSONB for structured outputs; scoped agent_operations schema |
| **Backend API** | FastAPI (Python 3.13) | Async, webhook receiver, dialing worker |
| **Queue / Rate Control** | Redis + RQ (open-source) | Enforces 1 CPS Telnyx limit; exponential backoff |
| **Automation** | n8n (self-hosted, open-source) | Post-call trigger → DB update → CRM/calendar push |
| **Frontend Dashboard** | Next.js 14 (open-source) | Live call monitoring, campaign management |
| **Containerisation** | Docker Compose | All services in one stack |
| **CI** | GitHub Actions | Lint, test, Docker build on PR |

> **Open-source maximised:** Silero VAD, Deepgram SDK, Redis, RQ, n8n, Next.js, FastAPI, PostgreSQL.
> **Paid where irreplaceable:** Retell AI orchestration, GPT-4o Realtime, ElevenLabs v3, Telnyx SIP.

---

## 3. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  PostgreSQL                                                        │
│  campaigns | leads | dnc_registry | call_logs | call_transcripts  │
└────────────────────┬─────────────────────────────────────────────┘
                     │  batch query (pending leads, DNC-checked)
                     ▼
          ┌─────────────────────┐
          │  Dialing Worker     │  Redis/RQ · 1 CPS · timezone gate
          │  (FastAPI + RQ)     │  E.164 format · CNAM rotation
          └──────────┬──────────┘
                     │  POST /create-call (Retell AI API)
                     ▼
          ┌──────────────────────────────────────────┐
          │  Retell AI Orchestration                 │
          │  VAD → Deepgram STT → GPT-4o Realtime    │
          │  → ElevenLabs TTS → Telnyx SIP           │
          └──────────┬───────────────────────────────┘
                     │  Webhooks (call_started / call_ended / call_analyzed)
                     ▼
          ┌─────────────────────┐
          │  FastAPI Webhook    │  x-retell-signature verified
          │  Receiver           │  → update leads.status
          └──────────┬──────────┘
                     │  call_analyzed payload
                     ▼
          ┌─────────────────────┐
          │  Claude Sonnet      │  Post-call structured extraction
          │  (Anthropic API)    │  → JSONB → call_transcripts
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  n8n Automation     │  CRM update / SMS / calendar trigger
          └─────────────────────┘
```

---

## 4. Module Breakdown

| # | Module | Scope | Model |
|---|---|---|---|
| 0 | **audit** | Read all files; no code changes | Sonnet |
| 1 | **db-schema** | PostgreSQL schema, Alembic migrations, scoped role | Haiku |
| 2 | **dialing-worker** | RQ worker, DNC check, E.164, timezone gate, 1 CPS | Sonnet |
| 3 | **retell-integration** | Retell AI API client, agent config, dynamic variables | Sonnet |
| 4 | **webhook-receiver** | FastAPI endpoints, signature verification, status updates | Sonnet |
| 5 | **post-call-analysis** | Claude Sonnet extraction, JSONB write, structured output schema | Sonnet |
| 6 | **vad-pipeline** | Silero VAD wrapper, state machine (QUIET/STARTING/SPEAKING/STOPPING) | Sonnet |
| 7 | **conversation-prompts** | System prompt library, persona templates, objection scripts | Sonnet |
| 8 | **dashboard** | Next.js: live calls, campaign manager, KPI charts | Sonnet |
| 9 | **n8n-flows** | Post-call automation: CRM push, SMS follow-up, calendar booking | Haiku |
| 10 | **docker-compose** | Full stack orchestration, env management | Haiku |
| 11 | **evals** | Load test suite, latency profiling, DNC regression tests | Sonnet |

---

## 5. Database Schema

### Schema: `agent_operations` (LLM access scoped here only)

```sql
-- Table 1: Campaigns
CREATE TABLE agent_operations.campaigns (
    campaign_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name           VARCHAR(255) NOT NULL,
    status         VARCHAR(50)  DEFAULT 'draft',  -- draft|active|paused|completed
    prompt_template JSONB       NOT NULL,          -- persona + objections + flow steps
    llm_config     JSONB        NOT NULL,          -- model, temperature, max_tokens
    created_at     TIMESTAMPTZ  DEFAULT NOW()
);

-- Table 2: Leads (dialing queue)
CREATE TABLE agent_operations.leads (
    lead_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number   VARCHAR(20)  NOT NULL,          -- E.164 format
    first_name     VARCHAR(100),
    last_name      VARCHAR(100),
    company        VARCHAR(255),
    timezone       VARCHAR(50)  NOT NULL,          -- e.g. Asia/Kolkata
    campaign_id    UUID         REFERENCES agent_operations.campaigns(campaign_id),
    status         VARCHAR(50)  DEFAULT 'pending', -- pending|calling|completed|failed|failed_dnc
    retry_count    INTEGER      DEFAULT 0,
    next_retry_at  TIMESTAMPTZ,
    custom_vars    JSONB,                          -- injected into Retell dynamic variables
    created_at     TIMESTAMPTZ  DEFAULT NOW()
);

-- Table 3: DNC Registry (checked before every dial)
CREATE TABLE agent_operations.dnc_registry (
    dnc_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number   VARCHAR(20)  NOT NULL UNIQUE,
    added_at       TIMESTAMPTZ  DEFAULT NOW(),
    source         VARCHAR(100)                    -- manual|national_dnc|caller_request
);

-- Table 4: Call Logs (immutable telemetry)
CREATE TABLE agent_operations.call_logs (
    call_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id        UUID         REFERENCES agent_operations.leads(lead_id),
    retell_call_id VARCHAR(255),                  -- Retell AI's call ID
    start_time     TIMESTAMPTZ,
    end_time       TIMESTAMPTZ,
    duration_sec   INTEGER,
    disconnect_reason VARCHAR(100),
    recording_url  VARCHAR(500),
    created_at     TIMESTAMPTZ  DEFAULT NOW()
);

-- Table 5: Call Transcripts + Structured Extraction
CREATE TABLE agent_operations.call_transcripts (
    transcript_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id        UUID         REFERENCES agent_operations.call_logs(call_id),
    raw_transcript TEXT,
    structured_data JSONB,                        -- GPT-5 / Sonnet extraction output
    sentiment      VARCHAR(50),
    created_at     TIMESTAMPTZ  DEFAULT NOW()
);
```

### LLM Role (security boundary)
```sql
CREATE ROLE memories_role;
GRANT USAGE ON SCHEMA agent_operations TO memories_role;
GRANT SELECT, INSERT, UPDATE ON agent_operations.leads TO memories_role;
GRANT SELECT ON agent_operations.campaigns TO memories_role;
GRANT SELECT ON agent_operations.dnc_registry TO memories_role;
GRANT SELECT, INSERT ON agent_operations.call_logs TO memories_role;
GRANT SELECT, INSERT ON agent_operations.call_transcripts TO memories_role;
-- NO DROP, DELETE, TRUNCATE granted
```

---

## 6. VAD State Machine

```
QUIET ──(audio > threshold, sustained 200ms)──► STARTING
STARTING ──(200ms confirmed)──────────────────► SPEAKING  → stream to STT
SPEAKING ──(silence > 800ms)──────────────────► STOPPING  → signal LLM to respond
STOPPING ──(LLM audio starts)─────────────────► QUIET

Interrupt path:
  SPEAKING (agent) ──(user audio detected)──► HALT TTS stream
                                            ──► truncate LLM context to last word spoken
                                            ──► STARTING (user)
```

Implementation: **Silero VAD** (PyTorch, open-source, MIT licence) via `silero-vad` Python package.

---

## 7. Conversation Prompt Design

### Voice prompt rules (CRITICAL for naturalness)
- Max sentence length: 12 words
- No bullets, no lists, no special characters
- Spell out acronyms phonetically (e.g. "GCC" → "Gee See See")
- Include natural fillers: "umm", "got it", "let me check"
- Each step waits for user confirmation before advancing
- Agent role: junior operations assistant, NOT a sales closer

### Prompt structure template
```
PERSONA:
  Name: [agent name]
  Tone: friendly, professional, unhurried
  Pace: measured; never rush; silence is okay

OBJECTIVE (single sentence):
  [Verify X / Confirm Y / Qualify Z]

FLOW:
  Step 1: Greeting + identity check
  Step 2: Purpose statement (one sentence)
  Step 3: Wait for response — do NOT continue if no acknowledgement
  Step 4: [Core question]
  Step 5: Handle objection OR proceed
  Step 6: Close + next step

OBJECTIONS:
  "busy" → "Of course! Can I call back at a better time?"
  "not interested" → "Absolutely, I understand. Have a great day."

ESCAPE:
  Any anger / confusion → offer email follow-up → end call politely
```

---

## 8. Outbound Dialing Worker Logic

```python
# Pseudocode — worker loop
async def dial_worker():
    while True:
        # 1. Fetch batch (50 leads max)
        leads = await db.fetch("""
            SELECT l.* FROM agent_operations.leads l
            WHERE l.status = 'pending'
              AND l.next_retry_at <= NOW()
              AND NOT EXISTS (
                  SELECT 1 FROM agent_operations.dnc_registry d
                  WHERE d.phone_number = l.phone_number
              )
            ORDER BY l.created_at
            LIMIT 50
        """)

        # 2. Timezone gate (8am–9pm local)
        dialable = [l for l in leads if is_within_calling_hours(l.timezone)]

        # 3. Dispatch with 1 CPS rate limit
        for lead in dialable:
            await retell_client.create_call(
                to_number=lead.phone_number,
                agent_id=campaign.retell_agent_id,
                dynamic_variables={
                    "first_name": lead.first_name,
                    "company": lead.company,
                    **lead.custom_vars
                }
            )
            await db.update_lead_status(lead.lead_id, "calling")
            await asyncio.sleep(1.0)   # strict 1 CPS

        await asyncio.sleep(5)  # poll interval
```

---

## 9. Webhook Events

| Event | Handler Action |
|---|---|
| `call_started` | Update `leads.status` → `calling`; insert `call_logs` row |
| `transcript_updated` | Broadcast to dashboard WebSocket for live monitoring |
| `call_ended` | Update `call_logs` with duration, disconnect_reason, recording_url |
| `call_analyzed` | Dispatch to Claude Sonnet extraction → write `call_transcripts.structured_data` |

All webhooks verify `x-retell-signature` HMAC before processing.

---

## 10. Structured Output Schema (post-call extraction)

```json
{
  "intent_confirmed": true,
  "interest_level": "high|medium|low|none",
  "callback_requested": false,
  "callback_time": null,
  "objections_raised": ["too busy", "already have a provider"],
  "key_facts_captured": {
    "budget_approved": true,
    "decision_maker": true,
    "timeline": "Q3 2026"
  },
  "sentiment": "positive|neutral|negative",
  "call_outcome": "qualified|unqualified|callback|dnc_request|voicemail",
  "summary": "One-sentence summary of the call outcome."
}
```

If `call_outcome == "dnc_request"` → auto-insert into `dnc_registry`.

---

## 11. KPIs and Observability

| KPI | Target | Alert Threshold |
|---|---|---|
| End-to-end response latency | < 500ms | > 800ms sustained |
| First-5-second detection rate | < 20% | > 35% |
| Structured output completion | > 95% | < 85% |
| DNC scrub miss rate | 0% | Any non-zero |
| Call abandon rate (< 10s) | < 15% | > 25% |
| Average call duration | > 90s | < 30s sustained |

Dashboards in Next.js; metrics stored in `call_logs`.

---

## 12. Compliance Requirements

- DNC pre-dial check at database query level (SQL NOT EXISTS, not application logic)
- Calling hours enforced in dialing worker: 08:00–21:00 lead's local timezone
- Consent timestamp, disclosure text, IP address stored at lead import
- TCPA litigator scrub API integration (PossibleNOW or equivalent) at campaign start
- Audit trail: every lead status change logged with timestamp + actor
- Recording URLs stored; auto-purge after 90 days unless flagged

---

## 13. Folder Structure

```
D:\staging\voice-outbound-agent\
├── PRD.md                            ← this file
├── CLAUDE.md                         ← project AI rules
├── TOOLS.md
├── SKILLS.md
├── docker-compose.yml
├── .env.example
│
├── app/
│   ├── db-schema/                    ← Module 1: Alembic migrations
│   ├── dialing-worker/               ← Module 2: RQ worker
│   ├── retell-integration/           ← Module 3: Retell API client
│   ├── webhook-receiver/             ← Module 4: FastAPI webhooks
│   ├── post-call-analysis/           ← Module 5: Claude extraction
│   ├── vad-pipeline/                 ← Module 6: Silero VAD
│   ├── conversation-prompts/         ← Module 7: Prompt library
│   └── dashboard/                    ← Module 8: Next.js
│
├── n8n-flows/                        ← Module 9: exported n8n JSON
├── tasks/
│   ├── TASK-000-repo-init.md
│   └── TASK-001-db-schema.md
│
└── .claude/
    └── skills/
        └── task-create.md
```

---

## 14. Environment Variables

```env
# Retell AI
RETELL_API_KEY=
RETELL_WEBHOOK_SECRET=

# Telnyx SIP
TELNYX_API_KEY=
TELNYX_SIP_USERNAME=
TELNYX_SIP_PASSWORD=
TELNYX_FROM_NUMBER=+91XXXXXXXXXX   # E.164

# ElevenLabs
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=

# OpenAI
OPENAI_API_KEY=

# Anthropic (post-call analysis)
ANTHROPIC_API_KEY=

# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/voice_agent

# Redis
REDIS_URL=redis://localhost:6379

# App
WEBHOOK_BASE_URL=https://your-domain.com
PORT=8000
```

---

## 15. Build Phases

| Phase | Modules | Goal |
|---|---|---|
| 0 | audit | Read codebase; no changes |
| 1 | db-schema | Schema live; migrations passing |
| 2 | dialing-worker | Worker dials a test number correctly |
| 3 | retell-integration | Retell agent configured; call connects |
| 4 | webhook-receiver | All 4 events received and DB updated |
| 5 | post-call-analysis | Structured JSON extracted from transcript |
| 6 | vad-pipeline | VAD correctly detects speech onset/offset |
| 7 | conversation-prompts | 3 persona templates tested end-to-end |
| 8 | dashboard | Live call visible in browser |
| 9 | n8n-flows | Post-call triggers CRM update |
| 10 | docker-compose | Full stack starts with single `docker compose up` |
| 11 | evals | Load test 100 mock leads; all KPIs green |

---

*Last updated: 2026-05*
*Owner: Srinivas / Fidelitus Corp + SherpaVector*
