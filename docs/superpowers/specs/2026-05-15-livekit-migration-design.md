# LiveKit Agents Migration Design

> **For agentic workers:** This spec drives a full replacement of the Retell AI integration with LiveKit Agents. Use `superpowers:writing-plans` to produce the implementation plan before touching any code.

**Goal:** Replace Retell AI entirely with LiveKit Agents (Deepgram STT + Groq LLM + ElevenLabs TTS) for outbound PSTN calls via a Twilio SIP trunk, keeping all existing DB models, post-call analysis, dashboard, and DNC logic intact.

**Tech Stack:**
- LiveKit Cloud (free tier) — room server + SIP bridge
- LiveKit Agents Python SDK — agent worker process
- Deepgram nova-2 — STT (free $200 credit)
- Groq llama-3.3-70b-versatile — LLM (free tier)
- ElevenLabs — TTS (10k chars/month free)
- Twilio SIP Trunk — PSTN bridge (~$0.014/min)
- Existing: FastAPI, PostgreSQL, Redis, RQ, SQLAlchemy

---

## Architecture

### Call Flow

```
DialerWorker
  → LiveKitClient.create_room(name="call-{lead_id}", metadata={lead_id, campaign_id, first_name, last_name})
  → LiveKitClient.create_sip_participant(room_name, to_number, sip_trunk_id)
       → LiveKit SIP Service → Twilio SIP Trunk → PSTN → Lead's phone rings
  → Lead picks up
  → LiveKit dispatches agent job to our livekit_agent worker process
  → Agent joins room, runs: Deepgram STT → Groq LLM → ElevenLabs TTS
  → Conversation proceeds using campaign prompt_template
  → Call ends (lead hangs up or agent ends call)
  → Agent writes transcript to DB directly
  → LiveKit sends room_finished webhook → FastAPI
  → Webhook handler: update lead status → COMPLETED, queue post-call analysis RQ job
```

### Three Concurrent Processes

| Process | Entry point | Role |
|---|---|---|
| FastAPI | `uvicorn app.webhook_receiver.main:app` | Webhook receiver + Dashboard API |
| DialerWorker | `scripts/run_worker.py` | Poll DB, dispatch calls via LiveKit |
| LiveKit Agent | `scripts/run_agent.py` | Join rooms, run STT→LLM→TTS pipeline |

### Webhook Event Mapping

| LiveKit Event | Replaces Retell Event | Action |
|---|---|---|
| `room_started` | `call_started` | Insert Call row in DB |
| `participant_joined` (SIP type) | — | Update lead status → CALLING |
| `participant_left` (SIP type) | — | No-op (agent writes transcript on completion) |
| `room_finished` | `call_analyzed` + `call_ended` | Update lead → COMPLETED, queue RQ analysis job |

---

## Module: `app/livekit_agent/` (NEW)

### Files

**`app/livekit_agent/__init__.py`** — empty

**`app/livekit_agent/config.py`**
- Pydantic Settings class: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, `GROQ_API_KEY`, `ELEVENLABS_API_KEY`, `DATABASE_URL`
- Single `livekit_agent_settings` instance

**`app/livekit_agent/agent.py`**
- `SalesAgent(livekit.agents.Agent)` — holds system prompt, implements `on_enter()` with greeting
- `entrypoint(ctx: JobContext)` — async function:
  1. `await ctx.connect()`
  2. Parse `ctx.room.metadata` → lead metadata dict
  3. Fetch campaign `prompt_template` from DB using `campaign_id`
  4. Build system prompt from template + lead variables
  5. Create `AgentSession(stt=deepgram.STT(), llm=groq.LLM(), tts=elevenlabs.TTS())`
  6. `await session.start(ctx.room, agent=SalesAgent(system_prompt))`
  7. `await session.wait_for_completion()`
  8. Call `save_call_result(ctx, session)` to write transcript to DB

**`app/livekit_agent/transcript_writer.py`**
- `save_call_result(ctx, session)` — async function:
  - Builds transcript string from `session.chat_ctx.messages` (verify exact attribute against installed SDK version)
  - Finds the Call row by `room_name = ctx.room.name`
  - Inserts into `transcripts` table (same schema as today)
  - Updates `calls.duration_sec` from call elapsed time
  - Does NOT update lead status (webhook handler does that to avoid race)

### scripts/run_agent.py

```python
from livekit.agents import WorkerOptions, cli
from app.livekit_agent.agent import entrypoint

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

---

## Module: `app/dialing_worker/` (MODIFIED)

### Files Changed

**`app/dialing_worker/livekit_client.py`** (NEW — replaces `retell_client.py`)
- `LiveKitClient(url, api_key, api_secret, sip_trunk_id)`
- `async create_room(room_name, metadata) -> Room`
  - `api.room.create_room(CreateRoomRequest(name=room_name, metadata=json.dumps(metadata)))`
- `async create_sip_participant(room_name, to_number) -> None`
  - `api.sip.create_sip_participant(CreateSIPParticipantRequest(sip_trunk_id=..., sip_call_to=to_number, room_name=room_name))`
- `async close()` — close API client
- Error handling: wrap `livekit.api` exceptions → `DialerError(retriable=True/False)`

**`app/dialing_worker/errors.py`** (MODIFIED)
- Rename `RetellAPIError` → `DialerError`
- Keep `retriable: bool` and `message: str` fields
- Update all imports in `worker.py`

**`app/dialing_worker/config.py`** (MODIFIED)
- Remove: `RETELL_API_KEY`, `RETELL_BASE_URL`, `RETELL_TIMEOUT_SEC`
- Add: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_SIP_TRUNK_ID`

**`app/dialing_worker/worker.py`** (MODIFIED)
- Replace `self.retell_client = RetellClient(...)` → `self.livekit_client = LiveKitClient(...)`
- Replace `_dispatch_call` body:
  ```python
  room_name = f"call-{lead.id}"
  metadata = {
      "lead_id": str(lead.id),
      "campaign_id": str(lead.campaign_id),
      "first_name": lead.first_name or "",
      "last_name": lead.last_name or "",
  }
  await self.livekit_client.create_room(room_name, metadata)
  await self.livekit_client.create_sip_participant(room_name, lead.phone_number)
  call_log = Call(lead_id=lead.id, retell_call_id=room_name)  # room_name stored in retell_call_id column
  ```
- Replace `RetellAPIError` → `DialerError` in error handler
- Replace `await self.retell_client.close()` → `await self.livekit_client.close()`

**`app/dialing_worker/dynamic_variables.py`** (DELETED)
- Was Retell-specific. Agent reads lead metadata directly from room metadata dict.

**`app/dialing_worker/retell_client.py`** (DELETED)

---

## Module: `app/webhook_receiver/` (MODIFIED)

### Signature Verification

**`app/webhook_receiver/signature_verifier.py`** (REPLACED)
```python
from livekit.api import WebhookReceiver
from livekit.api.webhook import WebhookEvent

def get_webhook_receiver(api_key: str, api_secret: str) -> WebhookReceiver:
    return WebhookReceiver(api_key=api_key, api_secret=api_secret)

def verify_livekit_webhook(body: bytes, auth_header: str, receiver: WebhookReceiver) -> WebhookEvent:
    return receiver.receive(body.decode(), auth_header)  # raises on invalid JWT
```

### Router

**`app/webhook_receiver/router.py`** (MODIFIED)
- Single endpoint: `POST /webhook/livekit` (replaces `POST /webhook`)
- Reads raw body + `Authorization` header
- Calls `verify_livekit_webhook()` → `WebhookEvent`
- Dispatches to handler by `event.event` field

### Handlers (REPLACED)

Delete: `call_started.py`, `call_ended.py`, `transcript_updated.py`, `call_analyzed.py`

Create:

**`app/webhook_receiver/handlers/room_started.py`**
- Extracts `room_name` from `event.room.name`
- Inserts `Call(lead_id=..., retell_call_id=room_name)` — lead_id from room metadata
- Broadcasts `call_started` event to dashboard WebSocket

**`app/webhook_receiver/handlers/participant_joined.py`**
- Only acts on SIP participants (`event.participant.kind == ParticipantKind.SIP`)
- Updates lead status → `CALLING`

**`app/webhook_receiver/handlers/room_finished.py`**
- Updates lead status → `COMPLETED`
- Calls `queue_service.enqueue_analysis(call_id)` — same as today
- Broadcasts `call_ended` to dashboard WebSocket

### Schemas (REPLACED)

Delete all 4 Retell schemas. LiveKit's SDK provides `WebhookEvent` directly — no custom Pydantic schemas needed.

---

## Configuration Changes

### `.env` additions
```
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxx
LIVEKIT_API_SECRET=<secret>
LIVEKIT_SIP_TRUNK_ID=ST_xxxxxxxxxxxx
DEEPGRAM_API_KEY=<key>
GROQ_API_KEY=<key>
ELEVENLABS_API_KEY=<key>
```

### `.env` removals
```
RETELL_API_KEY
RETELL_WEBHOOK_SECRET
```

### `docker-compose.yml`
Add `livekit_agent` service:
```yaml
livekit_agent:
  build:
    context: .
    dockerfile: Dockerfile.worker
  command: python scripts/run_agent.py
  env_file: .env
  depends_on: [postgres, redis]
  restart: unless-stopped
```

### One-time console setup (not automated)
1. LiveKit Cloud: create project, note `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
2. Twilio: create SIP Trunk, note SID and credentials
3. LiveKit Cloud → SIP → create Outbound Trunk pointing to Twilio, note `LIVEKIT_SIP_TRUNK_ID`
4. LiveKit Cloud → Webhooks → set URL to `https://<ngrok>/webhook/livekit`

---

## What Does NOT Change

- `app/models/` — all DB models unchanged
- `app/post_call_analysis/` — unchanged, reads same `transcripts` table
- `app/dashboard/` — Next.js dashboard unchanged
- `app/dashboard_api/` — unchanged (live calls query uses `retell_call_id` column which now holds `room_name`)
- `app/db/` — unchanged
- DNC filtering logic — unchanged (SQL NOT EXISTS)
- 1 CPS rate limit — unchanged (`asyncio.sleep(1.0)` in worker)
- Timezone gate — unchanged
- RQ post-call analysis queue — unchanged

---

## Dependencies to Add

```
livekit>=0.18
livekit-agents>=0.12
livekit-plugins-deepgram
livekit-plugins-elevenlabs
livekit-plugins-openai   # used for Groq via OpenAI-compatible API (groq.LLM sets base_url internally)
```
Note: verify `livekit-plugins-groq` exists as a standalone package — if not, `livekit-plugins-openai` with `base_url="https://api.groq.com/openai/v1"` is the fallback.

Remove: none (httpx stays, used elsewhere)
