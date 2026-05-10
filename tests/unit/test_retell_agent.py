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
