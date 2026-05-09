# CLAUDE.md - voice-outbound-agent
# Extends ~/.claude/CLAUDE.md. Never contradicts it.
# Read PRD.md FIRST before any session. It is the source of truth.

## Stack
Python 3.13, FastAPI, PostgreSQL 16, Redis, Docker, Next.js 14, Retell AI, Telnyx SIP, ElevenLabs TTS, Silero VAD, Anthropic Claude Sonnet

## Current Phase: 6 (conversation-prompts) — NEXT

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

**Phase 6 (conversation-prompts):** NEXT - system prompt library, persona templates, objection scripts
  - PRD Module 7 — see PRD.md §7 for prompt design rules
  - Target dir: app/conversation_prompts/
  - Start with brainstorming skill, then writing-plans, then subagent-driven-development

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
