# tests/unit/test_webhook_services.py
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.webhook_receiver.services.call_log_service import upsert_call_log, update_call_end
from app.webhook_receiver.services.lead_service import set_lead_status
from app.webhook_receiver.services.transcript_service import create_transcript
from app.webhook_receiver.services.queue_service import enqueue_analysis
from app.models.call import Call, CallStatus
from app.models.contact import Contact, ContactStatus
from app.models.transcript import Transcript


def _make_mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()
    return session


class TestUpsertCallLog:
    @pytest.mark.asyncio
    async def test_updates_existing_call_log(self):
        existing = MagicMock(spec=Call)
        existing.start_time = None

        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute.return_value = result_mock

        now = datetime.now(tz=timezone.utc)
        result = await upsert_call_log(session, "retell_001", now)

        assert result is existing
        assert existing.start_time == now
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_call_log_when_not_found(self):
        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        lead_id = uuid.uuid4()
        now = datetime.now(tz=timezone.utc)
        result = await upsert_call_log(session, "retell_002", now, lead_id=lead_id)

        session.add.assert_called_once()
        added_call = session.add.call_args[0][0]
        assert added_call.retell_call_id == "retell_002"
        assert added_call.lead_id == lead_id

    @pytest.mark.asyncio
    async def test_raises_if_no_lead_id_and_not_found(self):
        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        with pytest.raises(ValueError, match="lead_id"):
            await upsert_call_log(session, "retell_003", datetime.now(tz=timezone.utc))


class TestUpdateCallEnd:
    @pytest.mark.asyncio
    async def test_updates_found_call(self):
        existing = MagicMock(spec=Call)
        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute.return_value = result_mock

        now = datetime.now(tz=timezone.utc)
        result = await update_call_end(session, "retell_001", now, 60, "user_hangup", "https://rec.mp3")

        assert result is existing
        assert existing.end_time == now
        assert existing.duration_sec == 60
        assert existing.disconnect_reason == "user_hangup"
        assert existing.recording_url == "https://rec.mp3"

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self):
        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        result = await update_call_end(session, "missing", datetime.now(tz=timezone.utc), None, None, None)
        assert result is None


class TestSetLeadStatus:
    @pytest.mark.asyncio
    async def test_executes_update(self):
        session = _make_mock_session()
        result = MagicMock()
        result.rowcount = 1
        session.execute.return_value = result
        lead_id = uuid.uuid4()
        await set_lead_status(session, lead_id, ContactStatus.COMPLETED)
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_warns_when_no_rows_matched(self):
        session = _make_mock_session()
        result = MagicMock()
        result.rowcount = 0
        session.execute.return_value = result
        lead_id = uuid.uuid4()
        with patch("app.webhook_receiver.services.lead_service.logger") as mock_logger:
            await set_lead_status(session, lead_id, ContactStatus.COMPLETED)
            mock_logger.warning.assert_called_once()
            call_kwargs = mock_logger.warning.call_args
            assert str(lead_id) in str(call_kwargs)


class TestCreateTranscript:
    @pytest.mark.asyncio
    async def test_adds_transcript_to_session(self):
        session = _make_mock_session()
        # SELECT returns nothing → new transcript created
        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = None
        session.execute.return_value = select_result

        call_id = uuid.uuid4()
        result = await create_transcript(session, call_id, "Agent: Hi\nUser: Hello")
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.call_id == call_id
        assert added.raw_transcript == "Agent: Hi\nUser: Hello"
        assert added.structured_data is None

    @pytest.mark.asyncio
    async def test_updates_existing_transcript(self):
        session = _make_mock_session()
        existing = MagicMock(spec=Transcript)
        existing.raw_transcript = "old"
        existing.structured_data = None
        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = existing
        session.execute.return_value = select_result

        returned = await create_transcript(session, uuid.uuid4(), "new text")
        assert returned is existing
        assert existing.raw_transcript == "new text"
        session.add.assert_not_called()
        session.flush.assert_called_once()


class TestEnqueueAnalysis:
    @pytest.mark.asyncio
    async def test_enqueues_without_error(self):
        call_id = uuid.uuid4()
        with patch("app.webhook_receiver.services.queue_service._enqueue_sync") as mock_enqueue:
            await enqueue_analysis("redis://localhost:6379", call_id)
        mock_enqueue.assert_called_once_with("redis://localhost:6379", str(call_id))

    @pytest.mark.asyncio
    async def test_logs_error_on_redis_failure(self):
        call_id = uuid.uuid4()
        with patch(
            "app.webhook_receiver.services.queue_service._enqueue_sync",
            side_effect=Exception("Redis down"),
        ):
            # Should not raise — error is logged, not re-raised
            await enqueue_analysis("redis://localhost:6379", call_id)
