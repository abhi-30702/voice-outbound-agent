import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.dialing_worker.livekit_client import LiveKitClient
from app.dialing_worker.errors import DialerError


@pytest.fixture
def mock_lk_api():
    with patch("app.dialing_worker.livekit_client.LiveKitAPI") as MockAPI:
        instance = MagicMock()
        instance.room = MagicMock()
        instance.room.create_room = AsyncMock(return_value=MagicMock(name="call-abc"))
        instance.sip = MagicMock()
        instance.sip.create_sip_participant = AsyncMock(return_value=MagicMock())
        instance.aclose = AsyncMock()
        MockAPI.return_value = instance
        yield instance


@pytest.fixture
def client(mock_lk_api):
    return LiveKitClient(
        url="wss://test.livekit.cloud",
        api_key="key",
        api_secret="secret",
        sip_trunk_id="ST_123",
    )


@pytest.mark.asyncio
async def test_create_room_calls_api(client, mock_lk_api):
    await client.create_room("call-abc", {"lead_id": "lead-1"})
    mock_lk_api.room.create_room.assert_called_once()
    call_kwargs = mock_lk_api.room.create_room.call_args[0][0]
    assert call_kwargs.name == "call-abc"
    assert json.loads(call_kwargs.metadata)["lead_id"] == "lead-1"


@pytest.mark.asyncio
async def test_create_sip_participant_calls_api(client, mock_lk_api):
    await client.create_sip_participant("call-abc", "+12025550101")
    mock_lk_api.sip.create_sip_participant.assert_called_once()
    req = mock_lk_api.sip.create_sip_participant.call_args[0][0]
    assert req.sip_trunk_id == "ST_123"
    assert req.sip_call_to == "+12025550101"
    assert req.room_name == "call-abc"


@pytest.mark.asyncio
async def test_create_room_raises_dialer_error_on_failure(client, mock_lk_api):
    mock_lk_api.room.create_room.side_effect = Exception("connection refused")
    with pytest.raises(DialerError) as exc_info:
        await client.create_room("call-abc", {})
    assert exc_info.value.retriable is True


@pytest.mark.asyncio
async def test_create_sip_participant_raises_dialer_error_on_failure(client, mock_lk_api):
    mock_lk_api.sip.create_sip_participant.side_effect = Exception("sip trunk unreachable")
    with pytest.raises(DialerError) as exc_info:
        await client.create_sip_participant("call-abc", "+12025550101")
    assert exc_info.value.retriable is True


@pytest.mark.asyncio
async def test_close_calls_aclose(client, mock_lk_api):
    await client.close()
    mock_lk_api.aclose.assert_called_once()
