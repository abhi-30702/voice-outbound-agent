import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.post_call_analysis.worker import _run_analysis
from app.post_call_analysis.schemas import ExtractionResult

CALLBACK_EXTRACTION = ExtractionResult(
    call_outcome="callback_requested",
    callback_time="2026-05-10T10:00:00+05:30",
    objections_raised=["too busy"],
    next_action="Schedule a callback for tomorrow morning.",
    summary="Lead asked for a callback.",
    sentiment_reason="Positive tone throughout.",
    lead_temperature="hot",
    sentiment="positive",
    dnc_requested=False,
)


def _make_factory():
    call_id = uuid.uuid4()

    transcript = MagicMock()
    transcript.call_id = call_id
    transcript.raw_transcript = "Agent: Hi. User: Please call me back."

    call_obj = MagicMock()
    call_obj.id = call_id
    call_obj.lead_id = uuid.uuid4()

    lead = MagicMock()
    lead.id = call_obj.lead_id
    lead.phone_number = "+919876543210"
    lead.first_name = "Ravi"
    lead.last_name = "Sharma"
    lead.company = "ABC Corp"

    read_session = AsyncMock()
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = transcript
    r2 = MagicMock(); r2.scalar_one_or_none.return_value = call_obj
    r3 = MagicMock(); r3.scalar_one_or_none.return_value = lead
    read_session.execute = AsyncMock(side_effect=[r1, r2, r3])
    read_cm = AsyncMock()
    read_cm.__aenter__ = AsyncMock(return_value=read_session)
    read_cm.__aexit__ = AsyncMock(return_value=False)

    write_session = AsyncMock()
    write_session.execute = AsyncMock()
    begin_cm = AsyncMock()
    begin_cm.__aenter__ = AsyncMock(return_value=None)
    begin_cm.__aexit__ = AsyncMock(return_value=False)
    write_session.begin = MagicMock(return_value=begin_cm)
    write_cm = AsyncMock()
    write_cm.__aenter__ = AsyncMock(return_value=write_session)
    write_cm.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(side_effect=[read_cm, write_cm])
    return factory, transcript.call_id


@pytest.mark.asyncio
async def test_run_analysis_calls_notify_after_db_writes():
    factory, call_id = _make_factory()
    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude", return_value=CALLBACK_EXTRACTION):
            with patch("app.post_call_analysis.worker.scan", return_value=False):
                with patch("app.post_call_analysis.worker._notify_n8n", new_callable=AsyncMock) as mock_notify:
                    await _run_analysis(str(call_id))
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_payload_contains_required_keys():
    factory, call_id = _make_factory()
    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude", return_value=CALLBACK_EXTRACTION):
            with patch("app.post_call_analysis.worker.scan", return_value=False):
                with patch("app.post_call_analysis.worker._notify_n8n", new_callable=AsyncMock) as mock_notify:
                    await _run_analysis(str(call_id))
    payload = mock_notify.call_args[0][0]
    required = (
        "call_id", "lead_id", "phone_number", "first_name", "last_name",
        "company", "call_outcome", "callback_requested", "callback_time",
        "summary", "lead_temperature", "sentiment", "objections_raised", "next_action",
    )
    for key in required:
        assert key in payload, f"Missing key in n8n payload: {key}"
    assert payload["callback_requested"] is True
    assert payload["call_outcome"] == "callback_requested"


@pytest.mark.asyncio
async def test_notify_not_called_when_transcript_missing():
    call_id = uuid.uuid4()
    read_session = AsyncMock()
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = None
    read_session.execute = AsyncMock(return_value=r1)
    read_cm = AsyncMock()
    read_cm.__aenter__ = AsyncMock(return_value=read_session)
    read_cm.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=read_cm)

    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._notify_n8n", new_callable=AsyncMock) as mock_notify:
            await _run_analysis(str(call_id))
    mock_notify.assert_not_awaited()
