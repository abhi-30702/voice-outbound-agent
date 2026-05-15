import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


def make_event(event_type: str, room_name: str, metadata: dict | None = None, participant_kind: int | None = None):
    event = MagicMock()
    event.event = event_type
    event.room = MagicMock()
    event.room.name = room_name
    event.room.metadata = json.dumps(metadata or {})
    if participant_kind is not None:
        event.participant = MagicMock()
        event.participant.kind = participant_kind
    else:
        event.participant = None
    return event


@pytest.mark.asyncio
async def test_room_started_creates_call_log():
    from app.webhook_receiver.handlers.room_started import handle_room_started
    lead_id = str(uuid4())
    campaign_id = str(uuid4())
    event = make_event("room_started", f"call-{lead_id}", {"lead_id": lead_id, "campaign_id": campaign_id})

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock()
    mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.webhook_receiver.handlers.room_started.call_log_service") as mock_cls, \
         patch("app.webhook_receiver.handlers.room_started.lead_service") as mock_ls, \
         patch("app.webhook_receiver.handlers.room_started.broadcast"):
        mock_cls.upsert_call_log = AsyncMock(return_value=MagicMock(id=uuid4(), lead_id=uuid4()))
        mock_ls.set_lead_status = AsyncMock()
        await handle_room_started(event, mock_session_factory)
        mock_cls.upsert_call_log.assert_called_once()


@pytest.mark.asyncio
async def test_participant_joined_sip_sets_calling():
    from app.webhook_receiver.handlers.participant_joined import handle_participant_joined
    lead_id = str(uuid4())
    event = make_event("participant_joined", f"call-{lead_id}", {"lead_id": lead_id}, participant_kind=3)

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock()
    mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.webhook_receiver.handlers.participant_joined.lead_service") as mock_ls, \
         patch("app.webhook_receiver.handlers.participant_joined.call_log_service") as mock_cls:
        mock_cls.upsert_call_log = AsyncMock(return_value=MagicMock(lead_id=uuid4()))
        mock_ls.set_lead_status = AsyncMock()
        await handle_participant_joined(event, mock_session_factory)
        mock_ls.set_lead_status.assert_called_once()


@pytest.mark.asyncio
async def test_participant_joined_non_sip_is_noop():
    from app.webhook_receiver.handlers.participant_joined import handle_participant_joined
    event = make_event("participant_joined", "call-abc", {}, participant_kind=4)  # kind=4 is AGENT
    mock_session_factory = AsyncMock()

    with patch("app.webhook_receiver.handlers.participant_joined.lead_service") as mock_ls:
        mock_ls.set_lead_status = AsyncMock()
        await handle_participant_joined(event, mock_session_factory)
        mock_ls.set_lead_status.assert_not_called()


@pytest.mark.asyncio
async def test_room_finished_updates_lead_and_queues_analysis():
    from app.webhook_receiver.handlers.room_finished import handle_room_finished
    lead_id = str(uuid4())
    call_uuid = uuid4()
    event = make_event("room_finished", f"call-{lead_id}", {"lead_id": lead_id})

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock()
    mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.webhook_receiver.handlers.room_finished.call_log_service") as mock_cls, \
         patch("app.webhook_receiver.handlers.room_finished.lead_service") as mock_ls, \
         patch("app.webhook_receiver.handlers.room_finished.queue_service") as mock_qs, \
         patch("app.webhook_receiver.handlers.room_finished.broadcast"), \
         patch("app.webhook_receiver.handlers.room_finished.settings"):
        mock_cls.update_call_end = AsyncMock(return_value=MagicMock(id=call_uuid, lead_id=uuid4()))
        mock_ls.set_lead_status = AsyncMock()
        mock_qs.enqueue_analysis = AsyncMock()
        await handle_room_finished(event, mock_session_factory)
        mock_ls.set_lead_status.assert_called_once()
        mock_qs.enqueue_analysis.assert_called_once()
