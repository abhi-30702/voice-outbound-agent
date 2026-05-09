# Next Session - Quick Start Guide

## Current Status (as of 2026-05-09 EOD)

✅ **Module 1 (db-schema)**: Complete and merged to master
✅ **Module 2 (dialing-worker)**: Complete and merged to master
✅ **Module 3 (webhook-receiver)**: Complete and merged to master
✅ **Module 4 (post-call-analysis)**: Complete and merged to master
✅ **Module 5 (vad-pipeline)**: Complete and merged to master
⏳ **Module 6 (conversation-prompts)**: NEXT — not started

## Git State

**Current Branch:** master (clean, up to date with origin/master)
**Last commit:** e630e47 — fix: add state machine reset, double-start guard, and missing tests
**Test status:** 147 unit tests passing (fast suite)

## Immediate Action: Start Module 6 (conversation-prompts)

Module 6 builds the system prompt library per PRD.md §7:

```
Voice prompt rules (CRITICAL for naturalness):
- Max sentence length: 12 words
- No bullets, no lists, no special characters
- Spell out acronyms phonetically (e.g. "GCC" → "Gee See See")
- Include natural fillers: "umm", "got it", "let me check"
- Each step waits for user confirmation before advancing
- Agent role: junior operations assistant, NOT a sales closer

Prompt structure template:
  PERSONA: Name, tone (friendly/professional/unhurried), pace
  OBJECTIVE: Single sentence
  FLOW: Steps 1-6 (greeting → purpose → wait → question → objection → close)
  OBJECTIONS: busy, not interested, etc.
  ESCAPE: anger/confusion → email offer → end politely
```

**Target directory:** `app/conversation_prompts/`

**Start the session with:**
1. Read PRD.md §7 (Conversation Prompt Design) for requirements
2. Invoke brainstorming skill to design the module
3. Then writing-plans skill for the implementation plan
4. Then subagent-driven-development to execute

## What Was Built in Module 5 (vad-pipeline)

**Files created:**
- `app/vad_pipeline/schemas.py` — VADState enum, VADEvent frozen dataclass, VADConfig dataclass
- `app/vad_pipeline/state_machine.py` — Pure 4-state machine: QUIET/STARTING/SPEAKING/STOPPING, reset(), set_agent_speaking()
- `app/vad_pipeline/silero_wrapper.py` — Silero model wrapper: PCM bytes → float prob, 8/16kHz resampling, zero-padding, reset_states()
- `app/vad_pipeline/pipeline.py` — Async orchestrator: push_audio() / events queue / start() / stop()
- `app/vad_pipeline/README.md` — Usage docs and state transition table

**Files modified:**
- `requirements.txt` — added silero-vad>=4.0.0, torchaudio>=2.0.0

**Test counts:** 147 unit tests passing (28 new for Module 5; 6 slow Silero model tests excluded from fast run)

## Key Architecture Notes for Module 5

**State machine transitions:**
- QUIET → STARTING: first frame above onset_threshold (0.5)
- STARTING → SPEAKING: sustained 200ms above threshold
- STARTING → QUIET: false start (silence before 200ms)
- SPEAKING → STOPPING: first frame below offset_threshold (0.35)
- STOPPING → QUIET: sustained 800ms silence → signal LLM to respond
- STOPPING → SPEAKING: speech resumes before 800ms

**Hysteresis zone:** probs in [0.35, 0.5) in STOPPING hold position — no transition.

**Interrupt detection:** `pipeline.set_agent_speaking(True)` → any QUIET→STARTING emits `VADEvent(interrupted=True)`. Caller halts TTS and truncates LLM context.

**Pipeline lifecycle:** `start()` calls `wrapper.reset()` then `machine.reset()` — both LSTM and state machine reset for each new call stream. Double-start guard raises RuntimeError.

**Pipeline tests:** SileroWrapper is always mocked in fast tests — no model load. Run Silero tests separately with `python -m pytest tests/unit/test_vad_silero_wrapper.py -v -m slow`.

## Test Commands

Fast tests (no model load, ~3s):
```powershell
python -m pytest tests/unit/ --ignore=tests/unit/test_vad_silero_wrapper.py -v
```

All including slow Silero model tests (~30s first run):
```powershell
python -m pytest tests/unit/ -v
```

## GitHub

- Repo: https://github.com/abhi-30702/voice-outbound-agent
- Branch: master (all modules merged directly)
- gh CLI not available — use GitHub API with curl + PAT for future PRs
