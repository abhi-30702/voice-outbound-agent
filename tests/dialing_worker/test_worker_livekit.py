import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.dialing_worker.config import DialerConfig
from app.dialing_worker.worker import DialerWorker
from app.models.contact import Contact, ContactStatus
from app.models.campaign import Campaign


@pytest.fixture
def config():
    return DialerConfig(
        livekit_url="wss://test.livekit.cloud",
        livekit_api_key="key",
        livekit_api_secret="secret",
        livekit_sip_trunk_id="ST_123",
    )


@pytest.fixture
def worker(config):
    # Patch LiveKitClient so its __init__ doesn't try to open an aiohttp session
    # outside of an event loop (LiveKitAPI creates ClientSession eagerly).
    with patch("app.dialing_worker.worker.LiveKitClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        w = DialerWorker(config)
    return w


@pytest.mark.asyncio
async def test_dispatch_call_creates_room_and_sip(worker):
    lead_id = uuid4()
    campaign_id = uuid4()
    lead = Contact(
        id=lead_id,
        phone_number="+12025550101",
        first_name="John",
        last_name="Smith",
        timezone="America/New_York",
        campaign_id=campaign_id,
        status="PENDING",
        retry_count=0,
    )
    campaign = Campaign(id=campaign_id, name="Test", llm_config={})

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=campaign)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.merge = AsyncMock()

    worker.livekit_client = AsyncMock()
    worker.livekit_client.create_room = AsyncMock()
    worker.livekit_client.create_sip_participant = AsyncMock()

    worker.session_factory = MagicMock()

    await worker._dispatch_call(mock_session, lead)

    expected_room = f"call-{lead_id}"
    worker.livekit_client.create_room.assert_called_once_with(
        expected_room,
        {"lead_id": str(lead_id), "campaign_id": str(campaign_id),
         "first_name": "John", "last_name": "Smith"},
    )
    worker.livekit_client.create_sip_participant.assert_called_once_with(
        expected_room, "+12025550101"
    )
