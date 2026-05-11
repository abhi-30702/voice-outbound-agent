# Retell Integration Design

**Date:** 2026-05-10
**Module:** 3 (retell-integration)
**Status:** Approved

---

## 1. Goal

Extend the existing `app/dialing_worker/` with three targeted additions:

1. **`dynamic_variables.py`** — Typed `DynamicVariables` Pydantic model that maps lead + campaign fields into a validated, string-coerced dict for Retell call creation.
2. **`agent_manager.py`** — `sync_agent(campaign, client, db)` that creates or updates a Retell agent from a campaign's `prompt_template` / `llm_config` JSONB, writing `retell_agent_id` back to the DB.
3. **`RetellClient` extensions** — `create_agent()` and `update_agent()` HTTP methods added to the existing client in `retell_client.py`.

No new top-level module. No file moves. The dialing worker is updated to use `DynamicVariables` instead of its current ad-hoc dict construction.

---

## 2. Architecture

```
app/dialing_worker/
├── retell_client.py        ← extend: add create_agent(), update_agent()
├── agent_manager.py        ← NEW: build_agent_payload(), sync_agent()
├── dynamic_variables.py    ← NEW: DynamicVariables Pydantic model
└── worker.py               ← extend: use DynamicVariables.from_lead()
```

**Data flow — agent setup (one-time per campaign):**

```
Operator sets prompt_template + llm_config on campaign
    ↓
sync_agent(campaign, client, db)
    ↓
RetellClient.create_agent(payload)  [or update_agent if retell_agent_id exists]
    ↓
campaign.llm_config["retell_agent_id"] written to DB
```

**Data flow — call creation (per dial):**

```
DialerWorker._dispatch_call(lead, campaign)
    ↓
DynamicVariables.from_lead(lead, campaign).to_retell_dict()
    ↓
RetellClient.create_call(to_number, agent_id, dynamic_variables)
    ↓
Retell AI places call
```

**Dependency direction:** `worker.py` → `dynamic_variables.py` + `agent_manager.py` → `retell_client.py`. No reverse dependencies.

**`sync_agent()` is called explicitly** (management script or future API endpoint) — never automatically from the dialing worker hot path. The worker only reads `retell_agent_id` from `campaign.llm_config`.

---

## 3. `dynamic_variables.py`

```python
from pydantic import BaseModel, ConfigDict
from app.models.contact import Contact
from app.models.campaign import Campaign


class DynamicVariables(BaseModel):
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    phone_number: str = ""       # E.164
    campaign_name: str = ""

    model_config = ConfigDict(extra="allow")  # custom_vars keys pass through

    @classmethod
    def from_lead(cls, lead: Contact, campaign: Campaign) -> "DynamicVariables":
        base = {
            "first_name":    lead.first_name or "",
            "last_name":     lead.last_name or "",
            "company":       lead.company or "",
            "phone_number":  lead.phone_number,
            "campaign_name": campaign.name,
        }
        extras = lead.custom_vars or {}
        return cls(**base, **extras)

    def to_retell_dict(self) -> dict[str, str]:
        """Retell requires all dynamic variable values to be strings."""
        return {k: str(v) for k, v in self.model_dump().items()}
```

`extra="allow"` means any key in `lead.custom_vars` passes through to Retell without being declared upfront. `to_retell_dict()` coerces all values to strings as required by Retell's API.

---

## 4. `RetellClient` extensions (`retell_client.py`)

Two new async methods added to the existing `RetellClient` class. Same pattern as existing `create_call()`: async httpx, Bearer auth, `RetellAPIError` on failure.

```python
async def create_agent(self, payload: dict) -> dict:
    """POST /v2/create-agent — returns full agent object including agent_id."""
    async with self._client() as client:
        resp = await client.post("/v2/create-agent", json=payload)
        resp.raise_for_status()
        return resp.json()

async def update_agent(self, agent_id: str, payload: dict) -> dict:
    """PATCH /v2/update-agent/{agent_id} — returns updated agent object."""
    async with self._client() as client:
        resp = await client.patch(f"/v2/update-agent/{agent_id}", json=payload)
        resp.raise_for_status()
        return resp.json()
```

`RetellClient` remains a pure HTTP wrapper. Payload construction is the responsibility of `agent_manager.py`.

---

## 5. `agent_manager.py`

```python
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dialing_worker.retell_client import RetellClient
from app.models.campaign import Campaign


async def build_agent_payload(campaign: Campaign) -> dict:
    """Convert campaign prompt_template + llm_config into Retell agent API payload."""
    pt = campaign.prompt_template or {}
    lc = campaign.llm_config or {}
    return {
        "agent_name": campaign.name,
        "voice_id": lc.get("voice_id", ""),
        "response_engine": {
            "type": "retell-llm",
            "system_prompt": pt.get("system_prompt", ""),
        },
        "language": lc.get("language", "en-US"),
        "ambient_sound": lc.get("ambient_sound", None),
        "max_call_duration_ms": lc.get("max_call_duration_ms", 600_000),
    }


async def sync_agent(
    campaign: Campaign,
    client: RetellClient,
    db: AsyncSession,
) -> str:
    """Create or update the Retell agent for this campaign. Returns agent_id.

    Idempotent: safe to call repeatedly. Creates on first call, updates on
    subsequent calls. Writes retell_agent_id back to campaign.llm_config.
    """
    payload = await build_agent_payload(campaign)
    lc = campaign.llm_config or {}
    existing_id = lc.get("retell_agent_id")

    if existing_id:
        await client.update_agent(existing_id, payload)
        return existing_id
    else:
        result = await client.create_agent(payload)
        agent_id = result["agent_id"]
        await db.execute(
            update(Campaign)
            .where(Campaign.id == campaign.id)
            .values(llm_config={**lc, "retell_agent_id": agent_id})
        )
        await db.commit()
        return agent_id
```

### `prompt_template` expected keys

| Key | Type | Purpose |
|-----|------|---------|
| `system_prompt` | `str` | Full Retell LLM system prompt for this campaign |

### `llm_config` expected keys

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `retell_agent_id` | `str` | — | Set by `sync_agent()` on first create |
| `voice_id` | `str` | `""` | ElevenLabs / Retell voice ID |
| `language` | `str` | `"en-US"` | Call language |
| `ambient_sound` | `str \| None` | `None` | Optional background ambient |
| `max_call_duration_ms` | `int` | `600_000` | Max call length (10 min) |

---

## 6. Dialing Worker Update (`worker.py`)

Replace the existing ad-hoc `dynamic_variables` dict construction in `_dispatch_call()` with:

```python
from app.dialing_worker.dynamic_variables import DynamicVariables

# inside _dispatch_call():
dyn_vars = DynamicVariables.from_lead(lead, campaign).to_retell_dict()
await self.retell_client.create_call(
    to_number=lead.phone_number,
    agent_id=campaign.llm_config["retell_agent_id"],
    dynamic_variables=dyn_vars,
)
```

No other changes to `worker.py`.

---

## 7. Settings

`RETELL_API_KEY` is currently in `DialerConfig` (dataclass in `config.py`). It is **not** moved to `app/core/settings.py` — doing so would require refactoring the dialing worker's config loading, which is out of scope. `DialerConfig` already reads it from the environment via its own mechanism.

---

## 8. Testing Strategy

All tests use `respx` for HTTP mocking (already in `requirements.txt`). No live Retell API calls.

| Test file | Coverage |
|-----------|----------|
| `tests/unit/test_dynamic_variables.py` | `from_lead()` maps standard fields; `custom_vars` keys pass through via `extra="allow"`; missing fields default to `""`; `to_retell_dict()` coerces all values to strings including int/bool custom vars |
| `tests/unit/test_retell_agent.py` | `create_agent()` POSTs to `/v2/create-agent` with Bearer auth and correct JSON body; `update_agent()` PATCHes `/v2/update-agent/{id}`; `RetellAPIError` raised on 4xx; retriable=True on 429/5xx; retriable=False on other 4xx |
| `tests/unit/test_agent_manager.py` | `build_agent_payload()` maps `prompt_template.system_prompt` and all `llm_config` keys correctly; `sync_agent()` calls `create_agent()` and writes `retell_agent_id` to DB when none exists; `sync_agent()` calls `update_agent()` and does NOT write to DB when `retell_agent_id` already in `llm_config` |
| `tests/unit/test_worker.py` (existing) | Extend: verify `DynamicVariables.from_lead()` is used; existing call-creation tests continue passing |

**Target:** ~15 new tests. All 223 existing tests continue passing.

---

## 9. File Summary

| File | Action |
|------|--------|
| `app/dialing_worker/dynamic_variables.py` | Create |
| `app/dialing_worker/agent_manager.py` | Create |
| `app/dialing_worker/retell_client.py` | Extend: add `create_agent()`, `update_agent()` |
| `app/dialing_worker/worker.py` | Extend: use `DynamicVariables.from_lead()` |
| `tests/unit/test_dynamic_variables.py` | Create |
| `tests/unit/test_retell_agent.py` | Create |
| `tests/unit/test_agent_manager.py` | Create |
| `tests/unit/test_worker.py` | Extend (existing file) |

---

*Owner: Srinivas / Fidelitus Corp + SherpaVector*
