# app/webhook_receiver/handlers/room_started.py
import json
import logging
import uuid
from datetime import datetime, timezone

from livekit.api.webhook import WebhookEvent
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.dashboard_api.websocket import broadcast
from app.models.contact import ContactStatus
from app.webhook_receiver.services import call_log_service, lead_service

logger = logging.getLogger(__name__)


async def handle_room_started(
    event: WebhookEvent,
    session_factory: async_sessionmaker,
) -> None:
    room_name = event.room.name
    metadata = json.loads(event.room.metadata or "{}")
    raw_lead_id = metadata.get("lead_id")

    lead_id: uuid.UUID | None = None
    if raw_lead_id:
        try:
            lead_id = uuid.UUID(raw_lead_id)
        except ValueError:
            logger.warning(
                "Invalid lead_id in room metadata",
                extra={"room_name": room_name},
            )

    try:
        async with session_factory() as session:
            async with session.begin():
                call = await call_log_service.upsert_call_log(
                    session=session,
                    retell_call_id=room_name,
                    start_time=datetime.now(tz=timezone.utc),
                    lead_id=lead_id,
                )
                await lead_service.set_lead_status(
                    session=session,
                    lead_id=call.lead_id,
                    status=ContactStatus.CALLING,
                )
    except ValueError as exc:
        logger.warning(
            "Cannot record room_started — no lead_id",
            extra={"room_name": room_name, "error": str(exc)},
        )
        return

    logger.info("Handled room_started", extra={"room_name": room_name})
    await broadcast({"event": "call_started", "call_id": room_name, "payload": {}})
