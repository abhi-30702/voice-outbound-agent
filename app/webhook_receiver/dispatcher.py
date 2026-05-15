import logging

from livekit.api.webhook import WebhookEvent
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.webhook_receiver.handlers import room_started, participant_joined, room_finished

logger = logging.getLogger(__name__)


async def dispatch(event: WebhookEvent, session_factory: async_sessionmaker) -> None:
    event_type = event.event

    if event_type == "room_started":
        await room_started.handle_room_started(event, session_factory)
    elif event_type == "participant_joined":
        await participant_joined.handle_participant_joined(event, session_factory)
    elif event_type == "room_finished":
        await room_finished.handle_room_finished(event, session_factory)
    else:
        logger.debug("Unhandled LiveKit event type: %s", event_type)
