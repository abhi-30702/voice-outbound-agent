# tests/unit/test_dispatcher.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.webhook_receiver.dispatcher import dispatch
from app.webhook_receiver.schemas.base import BaseRetellEvent


def _base_event(event_type: str, call_id: str = "c1") -> BaseRetellEvent:
    return BaseRetellEvent(event=event_type, call_id=call_id)


def _raw(event_type: str, call_id: str = "c1") -> dict:
    return {"event": event_type, "call_id": call_id}


@pytest.mark.asyncio
async def test_call_started_dispatches_to_handler():
    factory = MagicMock()
    with patch("app.webhook_receiver.handlers.call_started.handle_call_started", AsyncMock()) as mock_h:
        await dispatch(_base_event("call_started"), _raw("call_started"), factory)
    mock_h.assert_called_once()


@pytest.mark.asyncio
async def test_call_ended_dispatches_to_handler():
    factory = MagicMock()
    with patch("app.webhook_receiver.handlers.call_ended.handle_call_ended", AsyncMock()) as mock_h:
        await dispatch(_base_event("call_ended"), _raw("call_ended"), factory)
    mock_h.assert_called_once()


@pytest.mark.asyncio
async def test_call_analyzed_dispatches_to_handler():
    factory = MagicMock()
    with patch("app.webhook_receiver.handlers.call_analyzed.handle_call_analyzed", AsyncMock()) as mock_h:
        await dispatch(_base_event("call_analyzed"), _raw("call_analyzed"), factory)
    mock_h.assert_called_once()


@pytest.mark.asyncio
async def test_transcript_updated_dispatches_to_handler():
    factory = MagicMock()
    with patch("app.webhook_receiver.handlers.transcript_updated.handle_transcript_updated", AsyncMock()) as mock_h:
        await dispatch(_base_event("transcript_updated"), _raw("transcript_updated"), factory)
    mock_h.assert_called_once()


@pytest.mark.asyncio
async def test_unknown_event_type_does_not_raise():
    factory = MagicMock()
    # Should complete without exception
    await dispatch(_base_event("call_something_future"), _raw("call_something_future"), factory)


@pytest.mark.asyncio
async def test_unknown_event_type_logs_warning(caplog):
    import logging
    factory = MagicMock()
    with caplog.at_level(logging.WARNING, logger="app.webhook_receiver.dispatcher"):
        await dispatch(_base_event("unknown_event_xyz"), _raw("unknown_event_xyz"), factory)
    assert any(
        hasattr(r, "event_type") and r.event_type == "unknown_event_xyz"
        for r in caplog.records
    )
