# app/webhook_receiver/dispatcher.py
import logging
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.webhook_receiver.schemas import (
    BaseRetellEvent,
    CallStartedPayload,
    CallEndedPayload,
    CallAnalyzedPayload,
    TranscriptUpdatedPayload,
)
from app.webhook_receiver.handlers import call_started, call_ended, call_analyzed, transcript_updated

logger = logging.getLogger(__name__)


async def dispatch(
    base_event: BaseRetellEvent,
    raw_dict: dict,
    session_factory: async_sessionmaker,
) -> None:
    event_type = base_event.event

    if event_type == "call_started":
        await call_started.handle_call_started(
            payload=CallStartedPayload(**raw_dict),
            session_factory=session_factory,
        )
    elif event_type == "call_ended":
        await call_ended.handle_call_ended(
            payload=CallEndedPayload(**raw_dict),
            session_factory=session_factory,
        )
    elif event_type == "call_analyzed":
        await call_analyzed.handle_call_analyzed(
            payload=CallAnalyzedPayload(**raw_dict),
            session_factory=session_factory,
        )
    elif event_type == "transcript_updated":
        await transcript_updated.handle_transcript_updated(
            payload=TranscriptUpdatedPayload(**raw_dict),
        )
    else:
        logger.warning(
            "Unknown webhook event type — ignoring",
            extra={"event_type": event_type, "call_id": base_event.call_id},
        )
