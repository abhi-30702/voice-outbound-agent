# Next Session - Quick Start Guide

## Current Status (as of 2026-05-08 EOD)

✅ **Module 1 (db-schema)**: Complete and merged to master
✅ **Module 2 (dialing-worker)**: Complete and merged to master
✅ **Module 3 (webhook-receiver)**: Complete and merged to master
✅ **Module 4 (post-call-analysis)**: Complete and merged to master
⏳ **Module 5 (vad-pipeline)**: NEXT — not started

## Git State

**Current Branch:** master (clean, up to date with origin/master)
**Last merged commit covers:** Module 4 post-call analysis
**dev branch:** still exists locally, same commits as master — safe to delete or reuse

## Immediate Action: Start Module 5 (vad-pipeline)

Module 5 implements the Silero VAD wrapper and a 4-state state machine per PRD.md §6:

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

**Implementation:** Silero VAD (PyTorch, open-source, MIT) via `silero-vad` Python package.
**Target directory:** `app/vad_pipeline/`

**Start the session with:**
1. Read PRD.md §6 (VAD State Machine) for requirements
2. Invoke brainstorming skill to design the module
3. Then writing-plans skill for the implementation plan
4. Then subagent-driven-development to execute

## What Was Built in Module 4 (post-call-analysis)

**Files created:**
- `app/post_call_analysis/worker.py` — `analyze_call` RQ job, `_run_analysis`, `_call_claude`, `_write_failure_flag`
- `app/post_call_analysis/schemas.py` — `ExtractionResult` Pydantic v2 (9 fields, Literal types)
- `app/post_call_analysis/prompts.py` — `SYSTEM_PROMPT` + `build_user_message()`
- `app/post_call_analysis/dnc_keywords.py` — `DNC_PHRASES` frozenset + `scan(transcript) -> bool`
- `app/post_call_analysis/README.md`

**Files modified:**
- `app/core/settings.py` — added `ANTHROPIC_API_KEY` field + startup warning
- `app/webhook_receiver/services/queue_service.py` — added `Retry(max=3, interval=[60,120,300])`

**Test counts:** 119 unit tests all passing (19 new for Module 4)

## Key Architecture Notes

**Cross-module dependency (dialing worker → webhook receiver):**
The dialing worker MUST pass `metadata={"lead_id": str(lead.id)}` in the Retell `create_call` API call.
The webhook receiver's `call_started` handler reads this to associate the call with a lead.

**RQ job path (must remain exact):**
`app.post_call_analysis.worker.analyze_call` — queue_service.py enqueues this exact string.

**Claude integration:**
- Model pinned: `CLAUDE_MODEL = "claude-sonnet-4-6"` in worker.py
- Sync client: `anthropic.Anthropic` (not AsyncAnthropic) — RQ jobs are synchronous
- Tool use forced via `tool_choice={"type": "any"}`

**DNC logic:**
- OR logic: `extraction.dnc_requested or scan(raw_transcript)` (belt-and-suspenders)
- Dead-letter: `getattr(job, "retries_left", 0) == 0` before re-raising

**Non-blocking follow-ups (tracked for future PR):**
1. Redis replay check in webhook receiver is not atomic (exists + setex); fix with SET NX PX
2. `call_analyzed` can arrive before `call_ended` — no ordering guarantee from Retell

## Test Command (verify everything still green)

```powershell
python -m pytest tests/unit/ -v --tb=short
```
Expected: 119 passed

## GitHub

- Repo: https://github.com/abhi-30702/voice-outbound-agent
- PR #1: merged (Modules 3 + 4)
- gh CLI not available — use GitHub API with curl + PAT for future PRs
