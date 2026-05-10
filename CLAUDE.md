# CLAUDE.md - voice-outbound-agent
# Extends ~/.claude/CLAUDE.md. Never contradicts it.
# Read PRD.md FIRST before any session. It is the source of truth.

## Stack
Python 3.13, FastAPI, PostgreSQL 16, Redis, Docker, Next.js 14, Retell AI, Telnyx SIP, ElevenLabs TTS, Silero VAD, Anthropic Claude Sonnet

## Current Phase: 8 (n8n-flows) — IN PROGRESS

### Phase Status Summary
**Phase 1 (db-schema):** COMPLETE - merged to master
**Phase 2 (dialing-worker):** COMPLETE - merged to master
  - Spec: docs/superpowers/specs/2026-05-07-dialing-worker-design.md
  - Plan: docs/superpowers/plans/2026-05-07-dialing-worker-implementation.md
  - Docs: app/dialing_worker/README.md

**Phase 3 (webhook-receiver):** COMPLETE - merged to master
  - Spec: docs/superpowers/specs/2026-05-08-webhook-receiver-design.md
  - Plan: docs/superpowers/plans/2026-05-08-webhook-receiver-implementation.md
  - Docs: app/webhook_receiver/README.md

**Phase 4 (post-call-analysis):** COMPLETE - merged to master
  - Spec: docs/superpowers/specs/2026-05-08-post-call-analysis-design.md
  - Plan: docs/superpowers/plans/2026-05-08-post-call-analysis-implementation.md
  - Docs: app/post_call_analysis/README.md
  - Key: analyze_call RQ job, Claude Sonnet tool use, DNC OR logic, dead-letter on retry exhaustion

**Phase 5 (vad-pipeline):** COMPLETE - merged to master
  - Spec: docs/superpowers/specs/2026-05-09-vad-pipeline-design.md
  - Plan: docs/superpowers/plans/2026-05-09-vad-pipeline-implementation.md
  - Docs: app/vad_pipeline/README.md
  - Key: layered arch (schemas→state_machine→silero_wrapper→pipeline), async queue interface, reset() on start(), interrupted flag

**Phase 6 (conversation-prompts):** COMPLETE - merged to master
  - Spec: docs/superpowers/specs/2026-05-09-conversation-prompts-design.md
  - Plan: docs/superpowers/plans/2026-05-09-conversation-prompts-implementation.md
  - Key: PromptTemplate JSONB dataclasses, PromptRenderer (lead var injection), ConstraintValidator (12-word/no-bullets/no-special-chars), 3 persona templates (real estate, recruitment, financial services), 31 tests

**Phase 7 (dashboard):** COMPLETE - PR open, pending merge to master
  - Branch: feature/module-7-dashboard
  - PR: https://github.com/abhi-30702/voice-outbound-agent/pull/new/feature/module-7-dashboard
  - Spec: docs/superpowers/specs/2026-05-09-dashboard-design.md
  - Plan: docs/superpowers/plans/2026-05-09-dashboard-implementation.md
  - Key: app/dashboard_api/ FastAPI module (REST + WebSocket), app/dashboard/ Next.js 14 (3 routes), ConnectionManager broadcast, Docker Compose service, 31 new tests (215 total)
  - Known minor issues (non-blocking): PATCH /campaigns/{id}/status returns lead_count=0; /api/calls/active missing phone_number

**Phase 8 (n8n-flows):** IN PROGRESS - subagent-driven development interrupted mid-execution
  - Branch: feature/module-7-dashboard (Module 8 work is on this same branch)
  - Spec: docs/superpowers/specs/2026-05-09-n8n-flows-design.md
  - Plan: docs/superpowers/plans/2026-05-09-n8n-flows-implementation.md
  - Tasks 1-4 DONE; Tasks 5-6 REMAINING (see NEXT_SESSION.md for exact resume point)
  - DO NOT re-run brainstorming or writing-plans — go straight to subagent-driven-development Task 5

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
