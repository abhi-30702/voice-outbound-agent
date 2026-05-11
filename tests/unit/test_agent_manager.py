import pytest
from unittest.mock import AsyncMock, MagicMock
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
    campaign.prompt_template = prompt_template if prompt_template is not None else {"system_prompt": "You are a helpful agent."}
    campaign.llm_config = llm_config if llm_config is not None else {}
    return campaign


def test_build_agent_payload_maps_system_prompt():
    campaign = _make_campaign(
        prompt_template={"system_prompt": "Call leads and qualify them."},
        llm_config={"voice_id": "voice-xyz", "language": "en-US"},
    )
    payload = build_agent_payload(campaign)
    assert payload["response_engine"]["system_prompt"] == "Call leads and qualify them."
    assert payload["response_engine"]["type"] == "retell-llm"


def test_build_agent_payload_maps_llm_config_fields():
    campaign = _make_campaign(
        llm_config={
            "voice_id": "v-001",
            "language": "hi-IN",
            "max_call_duration_ms": 300000,
            "ambient_sound": "office",
        }
    )
    payload = build_agent_payload(campaign)
    assert payload["voice_id"] == "v-001"
    assert payload["language"] == "hi-IN"
    assert payload["max_call_duration_ms"] == 300000
    assert payload["ambient_sound"] == "office"
    assert payload["agent_name"] == campaign.name


def test_build_agent_payload_defaults():
    campaign = _make_campaign(prompt_template={}, llm_config={})
    payload = build_agent_payload(campaign)
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

    expected_payload = build_agent_payload(campaign)
    mock_client.update_agent.assert_awaited_once_with("existing-agent-456", expected_payload)
    mock_client.create_agent.assert_not_awaited()
    mock_db.execute.assert_not_awaited()
    mock_db.commit.assert_not_awaited()
    assert result == "existing-agent-456"


@pytest.mark.asyncio
async def test_sync_agent_propagates_retell_api_error():
    from app.dialing_worker.errors import RetellAPIError

    campaign = _make_campaign(llm_config={})
    mock_client = AsyncMock()
    mock_client.create_agent = AsyncMock(
        side_effect=RetellAPIError(message="rate limited", retriable=True, status_code=429)
    )
    mock_db = AsyncMock()

    with pytest.raises(RetellAPIError):
        await sync_agent(campaign, mock_client, mock_db)

    mock_db.execute.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_agent_raises_and_logs_on_db_failure():
    campaign = _make_campaign(llm_config={})
    mock_client = AsyncMock()
    mock_client.create_agent = AsyncMock(return_value={"agent_id": "orphan-agent-789"})
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=RuntimeError("DB connection lost"))

    with pytest.raises(RuntimeError, match="DB connection lost"):
        await sync_agent(campaign, mock_client, mock_db)

    mock_client.create_agent.assert_awaited_once()
    mock_db.commit.assert_not_awaited()
