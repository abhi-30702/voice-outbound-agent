import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.post_call_analysis.worker import _run_analysis, analyze_call
from app.post_call_analysis.schemas import ExtractionResult

SAMPLE_EXTRACTION = ExtractionResult(
    call_outcome="interested",
    callback_time=None,
    objections_raised=["price"],
    next_action="Schedule follow-up",
    summary="Lead expressed interest but raised price concerns.",
    sentiment_reason="Positive tone throughout.",
    lead_temperature="warm",
    sentiment="positive",
    dnc_requested=False,
)

DNC_EXTRACTION = ExtractionResult(
    call_outcome="dnc_request",
    callback_time=None,
    objections_raised=[],
    next_action="No further action",
    summary="Lead asked to be removed from call list.",
    sentiment_reason="Hostile and frustrated.",
    lead_temperature="cold",
    sentiment="negative",
    dnc_requested=True,
)


def _make_session_factory(transcript=None, call_obj=None, lead=None):
    """Build mock session factory returning given DB objects from execute()."""
    call_id = uuid.uuid4()

    if transcript is None:
        transcript = MagicMock()
        transcript.call_id = call_id
        transcript.raw_transcript = "Agent: Hi. User: Sounds interesting."

    if call_obj is None:
        call_obj = MagicMock()
        call_obj.id = call_id
        call_obj.lead_id = uuid.uuid4()

    if lead is None:
        lead = MagicMock()
        lead.id = call_obj.lead_id
        lead.phone_number = "+15551234567"

    # Read session: three execute() calls in order (transcript, call, lead)
    read_session = AsyncMock()
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = transcript
    r2 = MagicMock(); r2.scalar_one_or_none.return_value = call_obj
    r3 = MagicMock(); r3.scalar_one_or_none.return_value = lead
    read_session.execute = AsyncMock(side_effect=[r1, r2, r3])

    read_cm = AsyncMock()
    read_cm.__aenter__ = AsyncMock(return_value=read_session)
    read_cm.__aexit__ = AsyncMock(return_value=False)

    # Write session
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
    return factory, transcript, call_obj, lead, write_session


@pytest.mark.asyncio
async def test_happy_path_executes_transcript_update():
    factory, transcript, call_obj, lead, write_session = _make_session_factory()

    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude", return_value=SAMPLE_EXTRACTION):
            with patch("app.post_call_analysis.worker.scan", return_value=False):
                await _run_analysis(str(transcript.call_id))

    # Only one write (UPDATE Transcript) — no DNC
    assert write_session.execute.call_count == 1


@pytest.mark.asyncio
async def test_dnc_from_claude_performs_three_writes():
    factory, transcript, call_obj, lead, write_session = _make_session_factory()

    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude", return_value=DNC_EXTRACTION):
            with patch("app.post_call_analysis.worker.scan", return_value=False):
                await _run_analysis(str(transcript.call_id))

    # Three writes: UPDATE transcript, INSERT dnc_registry, UPDATE leads
    assert write_session.execute.call_count == 3


@pytest.mark.asyncio
async def test_keyword_dnc_overrides_claude_false():
    factory, transcript, call_obj, lead, write_session = _make_session_factory()
    transcript.raw_transcript = "Please remove me from your list"

    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude", return_value=SAMPLE_EXTRACTION):
            with patch("app.post_call_analysis.worker.scan", return_value=True):
                await _run_analysis(str(transcript.call_id))

    # Keyword scan triggered DNC — three writes
    assert write_session.execute.call_count == 3


@pytest.mark.asyncio
async def test_transcript_not_found_skips_claude():
    call_id = uuid.uuid4()

    read_session = AsyncMock()
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = None
    read_session.execute = AsyncMock(return_value=r1)

    read_cm = AsyncMock()
    read_cm.__aenter__ = AsyncMock(return_value=read_session)
    read_cm.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=read_cm)

    with patch("app.post_call_analysis.worker.init_session_factory", AsyncMock(return_value=factory)):
        with patch("app.post_call_analysis.worker._call_claude") as mock_claude:
            await _run_analysis(str(call_id))
            mock_claude.assert_not_called()


def test_analyze_call_raises_on_failure_so_rq_can_retry():
    with patch("app.post_call_analysis.worker.asyncio.run", side_effect=Exception("Claude timeout")):
        with patch("app.post_call_analysis.worker.get_current_job", return_value=MagicMock(retries_left=1)):
            with pytest.raises(Exception, match="Claude timeout"):
                analyze_call("some-call-id")


def test_analyze_call_writes_failure_flag_on_last_retry():
    mock_job = MagicMock()
    mock_job.retries_left = 0

    # First asyncio.run (_run_analysis) raises; second (_write_failure_flag) succeeds
    with patch("app.post_call_analysis.worker.asyncio.run",
               side_effect=[Exception("Claude down"), None]) as mock_run:
        with patch("app.post_call_analysis.worker.get_current_job", return_value=mock_job):
            with pytest.raises(Exception, match="Claude down"):
                analyze_call("some-call-id")

    assert mock_run.call_count == 2
