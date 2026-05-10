# Retell Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `app/dialing_worker/` with a typed `DynamicVariables` model, agent create/update methods on `RetellClient`, an `agent_manager.py` with `sync_agent()`, and update the dialing worker to use `DynamicVariables` instead of an ad-hoc dict.

**Architecture:** Two new files (`dynamic_variables.py`, `agent_manager.py`) plus extensions to the existing `retell_client.py` and `worker.py`. No new top-level modules; no file moves. `RetellClient` stays a pure HTTP wrapper; business logic for payload construction lives in `agent_manager.py`; the dialing worker uses `DynamicVariables.from_lead()` to build call payloads.

**Tech Stack:** Python 3.13, Pydantic v2, httpx, SQLAlchemy async, pytest + pytest-asyncio, unittest.mock

---

## File Map

| File | Action |
|------|--------|
| `app/dialing_worker/dynamic_variables.py` | Create |
| `app/dialing_worker/agent_manager.py` | Create |
| `app/dialing_worker/retell_client.py` | Modify: add `create_agent()`, `update_agent()` |
| `app/dialing_worker/worker.py` | Modify: use `DynamicVariables.from_lead()` in `_dispatch_call()` |
| `tests/unit/test_dynamic_variables.py` | Create |
| `tests/unit/test_retell_agent.py` | Create |
| `tests/unit/test_agent_manager.py` | Create |

---

## Task 1: `DynamicVariables` model

**Files:**
- Create: `app/dialing_worker/dynamic_variables.py`
- Create: `tests/unit/test_dynamic_variables.py`

---

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_dynamic_variables.py`:

```python
import pytest
from unittest.mock import MagicMock

from app.dialing_worker.dynamic_variables import DynamicVariables


def _make_lead(
    phone_number="+919876543210",
    first_name="Ravi",
    last_name="Sharma",
    company="ABC Corp",
    custom_vars=None,
):
    lead = MagicMock()
    lead.phone_number = phone_number
    lead.first_name = first_name
    lead.last_name = last_name
    lead.company = company
    lead.custom_vars = custom_vars
    return lead


def _make_campaign(name="Test Campaign"):
    campaign = MagicMock()
    campaign.name = name
    return campaign


def test_from_lead_maps_standard_fields():
    lead = _make_lead()
    campaign = _make_campaign("My Campaign")
    dv = DynamicVariables.from_lead(lead, campaign)
    assert dv.first_name == "Ravi"
    assert dv.last_name == "Sharma"
    assert dv.company == "ABC Corp"
    assert dv.phone_number == "+919876543210"
    assert dv.campaign_name == "My Campaign"


def test_from_lead_none_fields_default_to_empty_string():
    lead = _make_lead(first_name=None, last_name=None, company=None)
    campaign = _make_campaign()
    dv = DynamicVariables.from_lead(lead, campaign)
    assert dv.first_name == ""
    assert dv.last_name == ""
    assert dv.company == ""


def test_from_lead_custom_vars_pass_through():
    lead = _make_lead(custom_vars={"product": "Pro Plan", "tier": "gold"})
    campaign = _make_campaign()
    dv = DynamicVariables.from_lead(lead, campaign)
    assert dv.model_dump()["product"] == "Pro Plan"
    assert dv.model_dump()["tier"] == "gold"


def test_from_lead_no_custom_vars():
    lead = _make_lead(custom_vars=None)
    campaign = _make_campaign()
    dv = DynamicVariables.from_lead(lead, campaign)
    d = dv.model_dump()
    assert "first_name" in d
    assert "phone_number" in d


def test_to_retell_dict_all_strings():
    lead = _make_lead(custom_vars={"score": 42, "active": True})
    campaign = _make_campaign()
    result = DynamicVariables.from_lead(lead, campaign).to_retell_dict()
    for v in result.values():
        assert isinstance(v, str), f"Expected str, got {type(v)} for value {v!r}"


def test_to_retell_dict_coerces_int_custom_var():
    lead = _make_lead(custom_vars={"score": 99})
    campaign = _make_campaign()
    result = DynamicVariables.from_lead(lead, campaign).to_retell_dict()
    assert result["score"] == "99"


def test_to_retell_dict_coerces_bool_custom_var():
    lead = _make_lead(custom_vars={"verified": True})
    campaign = _make_campaign()
    result = DynamicVariables.from_lead(lead, campaign).to_retell_dict()
    assert result["verified"] == "True"
```

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_dynamic_variables.py -v
```

Expected: `ImportError: cannot import name 'DynamicVariables'`

- [ ] **Step 3: Create `app/dialing_worker/dynamic_variables.py`**

```python
from pydantic import BaseModel, ConfigDict

from app.models.campaign import Campaign
from app.models.contact import Contact


class DynamicVariables(BaseModel):
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    phone_number: str = ""
    campaign_name: str = ""

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_lead(cls, lead: Contact, campaign: Campaign) -> "DynamicVariables":
        base = {
            "first_name": lead.first_name or "",
            "last_name": lead.last_name or "",
            "company": lead.company or "",
            "phone_number": lead.phone_number,
            "campaign_name": campaign.name,
        }
        extras = lead.custom_vars or {}
        return cls(**base, **extras)

    def to_retell_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in self.model_dump().items()}
```

- [ ] **Step 4: Run tests to confirm they pass**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_dynamic_variables.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```powershell
git add app/dialing_worker/dynamic_variables.py tests/unit/test_dynamic_variables.py
git commit -m "feat: add DynamicVariables model for typed Retell call payload"
```

---

## Task 2: `RetellClient` agent methods

**Files:**
- Modify: `app/dialing_worker/retell_client.py`
- Create: `tests/unit/test_retell_agent.py`

**Context:** `RetellClient` already has `create_call()` using `self.client` (an `httpx.AsyncClient` set up in `__init__`). The same error-handling pattern (TimeoutException → retriable, HTTPStatusError 429/5xx → retriable, other 4xx → not retriable, RequestError → retriable) applies to all new methods.

---

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_retell_agent.py`:

```python
import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock

from app.dialing_worker.retell_client import RetellClient
from app.dialing_worker.errors import RetellAPIError

AGENT_PAYLOAD = {
    "agent_name": "Test Agent",
    "voice_id": "voice-001",
    "response_engine": {"type": "retell-llm", "system_prompt": "You are a helpful assistant."},
    "language": "en-US",
    "ambient_sound": None,
    "max_call_duration_ms": 600000,
}


def _make_client() -> RetellClient:
    client = RetellClient(api_key="test-key")
    client.client = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_create_agent_posts_to_correct_endpoint():
    client = _make_client()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"agent_id": "agent-abc", **AGENT_PAYLOAD}
    client.client.post = AsyncMock(return_value=mock_resp)

    result = await client.create_agent(AGENT_PAYLOAD)

    client.client.post.assert_called_once()
    args, kwargs = client.client.post.call_args
    assert args[0] == "/v2/create-agent"
    assert kwargs["json"] == AGENT_PAYLOAD
    assert result["agent_id"] == "agent-abc"


@pytest.mark.asyncio
async def test_create_agent_includes_bearer_auth():
    client = RetellClient(api_key="my-secret-key")
    # Verify auth header is set on the underlying httpx client at init time
    assert client.client.headers["Authorization"] == "Bearer my-secret-key"


@pytest.mark.asyncio
async def test_update_agent_patches_correct_url():
    client = _make_client()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"agent_id": "agent-abc", **AGENT_PAYLOAD}
    client.client.patch = AsyncMock(return_value=mock_resp)

    result = await client.update_agent("agent-abc", AGENT_PAYLOAD)

    client.client.patch.assert_called_once()
    args, kwargs = client.client.patch.call_args
    assert args[0] == "/v2/update-agent/agent-abc"
    assert kwargs["json"] == AGENT_PAYLOAD
    assert result["agent_id"] == "agent-abc"


@pytest.mark.asyncio
async def test_create_agent_429_is_retriable():
    client = _make_client()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.json.return_value = {"message": "Rate limited"}
    mock_response.text = '{"message": "Rate limited"}'
    client.client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError("429", request=MagicMock(), response=mock_response)
    )

    with pytest.raises(RetellAPIError) as exc_info:
        await client.create_agent(AGENT_PAYLOAD)

    assert exc_info.value.retriable is True
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_create_agent_500_is_retriable():
    client = _make_client()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"message": "Internal error"}
    mock_response.text = '{"message": "Internal error"}'
    client.client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
    )

    with pytest.raises(RetellAPIError) as exc_info:
        await client.create_agent(AGENT_PAYLOAD)

    assert exc_info.value.retriable is True


@pytest.mark.asyncio
async def test_create_agent_400_not_retriable():
    client = _make_client()
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"message": "Bad request"}
    mock_response.text = '{"message": "Bad request"}'
    client.client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError("400", request=MagicMock(), response=mock_response)
    )

    with pytest.raises(RetellAPIError) as exc_info:
        await client.create_agent(AGENT_PAYLOAD)

    assert exc_info.value.retriable is False
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_update_agent_401_not_retriable():
    client = _make_client()
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"message": "Unauthorized"}
    mock_response.text = '{"message": "Unauthorized"}'
    client.client.patch = AsyncMock(
        side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response)
    )

    with pytest.raises(RetellAPIError) as exc_info:
        await client.update_agent("agent-abc", AGENT_PAYLOAD)

    assert exc_info.value.retriable is False


@pytest.mark.asyncio
async def test_create_agent_timeout_is_retriable():
    client = _make_client()
    client.client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    with pytest.raises(RetellAPIError) as exc_info:
        await client.create_agent(AGENT_PAYLOAD)

    assert exc_info.value.retriable is True
    assert exc_info.value.status_code is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_retell_agent.py -v
```

Expected: `AttributeError: 'RetellClient' object has no attribute 'create_agent'`

- [ ] **Step 3: Add `create_agent()` and `update_agent()` to `retell_client.py`**

Add these two methods to the `RetellClient` class, after the existing `create_call()` method and before `close()`:

```python
    async def create_agent(self, payload: dict) -> dict:
        """Create a new Retell AI agent.

        Args:
            payload: Agent configuration dict (agent_name, voice_id, response_engine, etc.)

        Returns:
            Created agent object from Retell API (contains agent_id)

        Raises:
            RetellAPIError: If API request fails
        """
        try:
            response = await self.client.post("/v2/create-agent", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            raise RetellAPIError(
                message=f"Retell API timeout: {str(e)}",
                retriable=True,
                status_code=None,
            ) from e
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            retriable = status_code in (429, 500, 502, 503, 504)
            try:
                error_body = e.response.json()
                error_msg = error_body.get("message", str(error_body))
            except (json.JSONDecodeError, ValueError):
                error_msg = e.response.text or str(e)
            raise RetellAPIError(
                message=f"Retell API error ({status_code}): {error_msg}",
                retriable=retriable,
                status_code=status_code,
            ) from e
        except httpx.RequestError as e:
            raise RetellAPIError(
                message=f"Retell API request failed: {str(e)}",
                retriable=True,
                status_code=None,
            ) from e

    async def update_agent(self, agent_id: str, payload: dict) -> dict:
        """Update an existing Retell AI agent.

        Args:
            agent_id: The Retell agent ID to update
            payload: Updated agent configuration dict

        Returns:
            Updated agent object from Retell API

        Raises:
            RetellAPIError: If API request fails
        """
        try:
            response = await self.client.patch(
                f"/v2/update-agent/{agent_id}", json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            raise RetellAPIError(
                message=f"Retell API timeout: {str(e)}",
                retriable=True,
                status_code=None,
            ) from e
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            retriable = status_code in (429, 500, 502, 503, 504)
            try:
                error_body = e.response.json()
                error_msg = error_body.get("message", str(error_body))
            except (json.JSONDecodeError, ValueError):
                error_msg = e.response.text or str(e)
            raise RetellAPIError(
                message=f"Retell API error ({status_code}): {error_msg}",
                retriable=retriable,
                status_code=status_code,
            ) from e
        except httpx.RequestError as e:
            raise RetellAPIError(
                message=f"Retell API request failed: {str(e)}",
                retriable=True,
                status_code=None,
            ) from e
```

- [ ] **Step 4: Run tests to confirm they pass**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_retell_agent.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Confirm existing retell_client tests still pass**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_retell_client.py -v
```

Expected: all existing tests pass (no regressions)

- [ ] **Step 6: Commit**

```powershell
git add app/dialing_worker/retell_client.py tests/unit/test_retell_agent.py
git commit -m "feat: add create_agent and update_agent to RetellClient"
```

---

## Task 3: `agent_manager.py`

**Files:**
- Create: `app/dialing_worker/agent_manager.py`
- Create: `tests/unit/test_agent_manager.py`

**Context:** `sync_agent()` is idempotent — reads `retell_agent_id` from `campaign.llm_config`. If present, calls `update_agent()`. If absent, calls `create_agent()`, gets the `agent_id` from the response, and writes it back to `campaign.llm_config` via SQLAlchemy `update()` + `commit()`. `build_agent_payload()` is pure and testable without any mocking.

---

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_agent_manager.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.dialing_worker.agent_manager import build_agent_payload, sync_agent


def _make_campaign(
    name="Campaign A",
    prompt_template=None,
    llm_config=None,
):
    campaign = MagicMock()
    campaign.id = uuid4()
    campaign.name = name
    campaign.prompt_template = prompt_template or {"system_prompt": "You are a helpful agent."}
    campaign.llm_config = llm_config or {}
    return campaign


@pytest.mark.asyncio
async def test_build_agent_payload_maps_system_prompt():
    campaign = _make_campaign(
        prompt_template={"system_prompt": "Call leads and qualify them."},
        llm_config={"voice_id": "voice-xyz", "language": "en-US"},
    )
    payload = await build_agent_payload(campaign)
    assert payload["response_engine"]["system_prompt"] == "Call leads and qualify them."
    assert payload["response_engine"]["type"] == "retell-llm"


@pytest.mark.asyncio
async def test_build_agent_payload_maps_llm_config_fields():
    campaign = _make_campaign(
        llm_config={
            "voice_id": "v-001",
            "language": "hi-IN",
            "max_call_duration_ms": 300000,
            "ambient_sound": "office",
        }
    )
    payload = await build_agent_payload(campaign)
    assert payload["voice_id"] == "v-001"
    assert payload["language"] == "hi-IN"
    assert payload["max_call_duration_ms"] == 300000
    assert payload["ambient_sound"] == "office"
    assert payload["agent_name"] == campaign.name


@pytest.mark.asyncio
async def test_build_agent_payload_defaults():
    campaign = _make_campaign(prompt_template={}, llm_config={})
    payload = await build_agent_payload(campaign)
    assert payload["language"] == "en-US"
    assert payload["max_call_duration_ms"] == 600_000
    assert payload["ambient_sound"] is None
    assert payload["voice_id"] == ""
    assert payload["response_engine"]["system_prompt"] == ""


@pytest.mark.asyncio
async def test_sync_agent_creates_when_no_agent_id():
    campaign = _make_campaign(llm_config={})
    mock_client = AsyncMock()
    mock_client.create_agent = AsyncMock(return_value={"agent_id": "new-agent-123"})
    mock_db = AsyncMock()

    result = await sync_agent(campaign, mock_client, mock_db)

    mock_client.create_agent.assert_awaited_once()
    mock_client.update_agent.assert_not_awaited()
    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()
    assert result == "new-agent-123"


@pytest.mark.asyncio
async def test_sync_agent_updates_when_agent_id_exists():
    campaign = _make_campaign(llm_config={"retell_agent_id": "existing-agent-456"})
    mock_client = AsyncMock()
    mock_client.update_agent = AsyncMock(return_value={"agent_id": "existing-agent-456"})
    mock_db = AsyncMock()

    result = await sync_agent(campaign, mock_client, mock_db)

    mock_client.update_agent.assert_awaited_once_with("existing-agent-456", await build_agent_payload(campaign))
    mock_client.create_agent.assert_not_awaited()
    mock_db.execute.assert_not_awaited()
    mock_db.commit.assert_not_awaited()
    assert result == "existing-agent-456"
```

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_agent_manager.py -v
```

Expected: `ImportError: cannot import name 'build_agent_payload'`

- [ ] **Step 3: Create `app/dialing_worker/agent_manager.py`**

```python
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dialing_worker.retell_client import RetellClient
from app.models.campaign import Campaign


async def build_agent_payload(campaign: Campaign) -> dict:
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
    payload = await build_agent_payload(campaign)
    lc = campaign.llm_config or {}
    existing_id = lc.get("retell_agent_id")

    if existing_id:
        await client.update_agent(existing_id, payload)
        return existing_id

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

- [ ] **Step 4: Run tests to confirm they pass**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_agent_manager.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```powershell
git add app/dialing_worker/agent_manager.py tests/unit/test_agent_manager.py
git commit -m "feat: add agent_manager with sync_agent and build_agent_payload"
```

---

## Task 4: Update `worker.py` to use `DynamicVariables`

**Files:**
- Modify: `app/dialing_worker/worker.py` (lines 177–182 in `_dispatch_call`)

**Context:** The current `_dispatch_call()` builds a plain dict for `dynamic_variables` manually. Replace this with `DynamicVariables.from_lead(lead, campaign).to_retell_dict()`.

Current code in `_dispatch_call()` (lines 177–191):

```python
        # Build dynamic variables from lead data + custom vars
        dynamic_variables = {
            "first_name": lead.first_name or "",
            "company": lead.company or "",
        }
        if lead.custom_vars:
            dynamic_variables.update(lead.custom_vars)

        # Call Retell API to create the call
        try:
            response = await self.retell_client.create_call(
                to_number=lead.phone_number,
                agent_id=campaign.llm_config.get(
                    "retell_agent_id", ""
                ),  # Simplified
                dynamic_variables=dynamic_variables,
            )
```

---

- [ ] **Step 1: Add the import to `worker.py`**

Add this import at the top of `app/dialing_worker/worker.py`, after the existing imports:

```python
from app.dialing_worker.dynamic_variables import DynamicVariables
```

The full imports block should look like:

```python
from app.db.session import get_session_factory
from app.dialing_worker.config import DialerConfig
from app.dialing_worker.dynamic_variables import DynamicVariables
from app.dialing_worker.errors import RetellAPIError
from app.dialing_worker.phone_utils import is_e164
from app.dialing_worker.retell_client import RetellClient
from app.dialing_worker.timezone_utils import is_within_calling_hours
from app.models import Contact, ContactStatus, Campaign, Call
```

- [ ] **Step 2: Replace the ad-hoc dict in `_dispatch_call()`**

Replace this block:

```python
        # Build dynamic variables from lead data + custom vars
        dynamic_variables = {
            "first_name": lead.first_name or "",
            "company": lead.company or "",
        }
        if lead.custom_vars:
            dynamic_variables.update(lead.custom_vars)

        # Call Retell API to create the call
        try:
            response = await self.retell_client.create_call(
                to_number=lead.phone_number,
                agent_id=campaign.llm_config.get(
                    "retell_agent_id", ""
                ),  # Simplified
                dynamic_variables=dynamic_variables,
            )
```

With this:

```python
        # Build typed dynamic variables from lead + campaign
        dynamic_variables = DynamicVariables.from_lead(lead, campaign).to_retell_dict()

        # Call Retell API to create the call
        try:
            response = await self.retell_client.create_call(
                to_number=lead.phone_number,
                agent_id=campaign.llm_config.get("retell_agent_id", ""),
                dynamic_variables=dynamic_variables,
            )
```

- [ ] **Step 3: Run the full unit test suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/ -q --tb=short
```

Expected: 238 passed (223 existing + 7 dynamic_variables + 8 retell_agent + 5 agent_manager = ~243; exact count may vary by 1-2), 1 pre-existing numpy skip, 0 failures.

If any tests fail, read the failure output and fix the root cause before proceeding.

- [ ] **Step 4: Commit**

```powershell
git add app/dialing_worker/worker.py
git commit -m "feat: use DynamicVariables in DialerWorker._dispatch_call"
```

---

## Acceptance Criteria

- [ ] `pytest tests/unit/ -q` → all new tests passing, 0 regressions
- [ ] `DynamicVariables.from_lead(lead, campaign).to_retell_dict()` returns `dict[str, str]` with all values as strings
- [ ] `custom_vars` keys from `lead.custom_vars` pass through via `extra="allow"`
- [ ] `RetellClient.create_agent()` POSTs to `/v2/create-agent` with correct Bearer auth
- [ ] `RetellClient.update_agent()` PATCHes `/v2/update-agent/{agent_id}`
- [ ] `sync_agent()` creates agent + writes `retell_agent_id` to DB when none exists
- [ ] `sync_agent()` updates agent + does NOT write to DB when `retell_agent_id` already in `llm_config`
- [ ] `DialerWorker._dispatch_call()` uses `DynamicVariables.from_lead()` — no ad-hoc dict
