# app/webhook_receiver/handlers/room_finished.py
import json
import logging
import uuid
from datetime import datetime, timezone

from livekit.api.webhook import WebhookEvent
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.settings import settings
from app.dashboard_api.websocket import broadcast
from app.models.contact import ContactStatus
from app.webhook_receiver.services import call_log_service, lead_service, queue_service

logger = logging.getLogger(__name__)


async def handle_room_finished(
    event: WebhookEvent,
    session_factory: async_sessionmaker,
) -> None:
    room_name = event.room.name
    call_uuid: uuid.UUID | None = None

    async with session_factory() as session:
        async with session.begin():
            call = await call_log_service.update_call_end(
                session=session,
                retell_call_id=room_name,
                end_time=datetime.now(tz=timezone.utc),
                duration_sec=None,
                disconnect_reason=None,
                recording_url=None,
            )
            if call is None:
                logger.warning(
                    "No call_log found for room_finished",
                    extra={"room_name": room_name},
                )
                return

            await lead_service.set_lead_status(
                session=session,
                lead_id=call.lead_id,
                status=ContactStatus.COMPLETED,
            )
            call_uuid = call.id

    await queue_service.enqueue_analysis(
        redis_url=settings.REDIS_URL,
        call_id=call_uuid,
    )
    logger.info("Handled room_finished", extra={"room_name": room_name})
    await broadcast({"event": "call_ended", "call_id": room_name, "payload": {}})
