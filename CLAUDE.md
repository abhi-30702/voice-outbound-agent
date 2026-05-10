# CLAUDE.md - voice-outbound-agent
# Extends ~/.claude/CLAUDE.md. Never contradicts it.
# Read PRD.md FIRST before any session. It is the source of truth.

## Stack
Python 3.13, FastAPI, PostgreSQL 16, Redis, Docker, Next.js 14, Retell AI, Telnyx SIP, ElevenLabs TTS, Silero VAD, Anthropic Claude Sonnet

## Current Phase: ALL COMPLETE — master pushed to origin; docker-compose + evals need PR to dev

### Phase Status Summary
**Phase 1 (db-schema):** COMPLETE - merged to dev
**Phase 2 (dialing-worker):** COMPLETE - merged to dev
**Phase 3 (webhook-receiver):** COMPLETE - merged to dev
**Phase 4 (post-call-analysis):** COMPLETE - merged to dev
**Phase 5 (vad-pipeline):** COMPLETE - merged to dev
**Phase 6 (conversation-prompts):** COMPLETE - merged to dev
**Phase 7 (dashboard):** COMPLETE - merged to dev (PR #2)
  - Key: app/dashboard_api/ FastAPI module (REST + WebSocket), app/dashboard/ Next.js 14 (3 routes), ConnectionManager broadcast, 31 new tests
**Phase 8 (n8n-flows):** COMPLETE - merged to dev (PR #2)
  - Key: _notify_n8n fire-and-forget notifier, n8n Docker service, 6-node flow (Sheets+SMS+Calendar), 8 new tests (223 total)
**Phase 9 (docker-compose):** COMPLETE - on master
  - Key: docker-compose.yml (6 services with healthchecks), Dockerfile.api, Dockerfile.worker, scripts/run_worker.py, .env.example, Makefile
**Phase 10 (evals — TASK-011):** COMPLETE - on master
  - Key: tests/evals/ — 5 pytest files (12 mock tests pass), locustfile.py (CPS load test), kpi_check.py (standalone DB KPI script)
  - DNC regression: 100-lead SQL gate test (needs real DB)
  - Worker rate limit: 1 CPS over 10 leads (elapsed ≥ 9s, create_call × 10)
  - Timezone gate: freezegun 5-timezone test
  - Structured output: 3 transcripts × ExtractionResult schema validation
  - Signature verification: valid=200, tampered=403, missing=422 (ASGI layer)

## Local Dev Restart (after reboot)
  1. `docker compose up -d redis`  — postgres16 starts automatically with Docker Desktop
  2. Set env vars + `.venv\Scripts\python -m uvicorn app.webhook_receiver.main:app --host 0.0.0.0 --port 8000`
  3. `cd app/dashboard && npm run dev`
  DB: postgres:password@localhost:5432/voice_agent (migrations at head)
  .env is NOT committed — reconfigure with real keys for production

## PRD Reference
  Location: PRD.md (project root)
  Read sections: Tech Stack, Module Breakdown, DB Schema, Dialing Worker Logic

## Module Boundaries (one session = one module)
  Session -> db-schema          : app/db-schema/ ONLY
  Session -> dialing-worker     : app/dialing-worker/ ONLY
  Session -> retell-integration : app/retell-integration/ ONLY
  Session -> webhook-receiver   : app/webhook-receiver/ ONLY
  Session -> post-call-analysis : app/post-call-analysis/ ONLY
  Session -> vad-pipeline       : app/vad-pipeline/ ONLY
  Session -> conversation-prompts : app/conversation-prompts/ ONLY
  Session -> dashboard          : app/dashboard/ ONLY
  Session -> n8n-flows          : n8n-flows/ ONLY
  Session -> docker-compose     : docker-compose.yml + Dockerfile per service
  Session -> evals              : tests/ ONLY
  Session -> debug              : one error + one file per session

## Key Architecture Rules
  - DNC check MUST be in SQL (NOT EXISTS), never application-level filtering
  - Dialing worker MUST enforce 1 CPS hard limit via asyncio.sleep(1.0)
  - Timezone gate MUST use lead.timezone; never assume IST
  - All webhook handlers MUST verify x-retell-signature HMAC
  - LLM DB access via memories_role ONLY (scoped schema: agent_operations)
  - Parameterised queries only - no string interpolation in SQL
  - No bare sockets; all telephony via Retell AI + Telnyx SDK

## Conversation Prompts Rule
  - Max sentence: 12 words
  - No bullets, no lists, no special chars in TTS text
  - Spell acronyms phonetically
  - Every step must WAIT for user acknowledgement before advancing

## Environment
  Windows + PowerShell
  Python 3.13 with venv at .venv/
  Node 20+ for Next.js dashboard
  Docker Desktop for containers

## Git
  main / dev / feature/TASK-XXX
  Format: [TASK-XXX] verb: what changed
  Never commit .env files
