# app/webhook_receiver/handlers/participant_joined.py
import json
import logging
import uuid

from livekit.api.webhook import WebhookEvent
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.contact import ContactStatus
from app.webhook_receiver.services import call_log_service, lead_service

logger = logging.getLogger(__name__)

SIP_PARTICIPANT_KIND = 3  # livekit.protocol.models.ParticipantInfo.Kind.SIP


async def handle_participant_joined(
    event: WebhookEvent,
    session_factory: async_sessionmaker,
) -> None:
    if event.participant is None or event.participant.kind != SIP_PARTICIPANT_KIND:
        return  # only act on SIP (lead) participants, not agent participants

    room_name = event.room.name
    metadata = json.loads(event.room.metadata or "{}")
    raw_lead_id = metadata.get("lead_id")
    if not raw_lead_id:
        logger.warning(
            "No lead_id in room metadata at participant_joined",
            extra={"room_name": room_name},
        )
        return

    try:
        lead_id = uuid.UUID(raw_lead_id)
    except ValueError:
        logger.warning(
            "Invalid lead_id in room metadata",
            extra={"room_name": room_name},
        )
        return

    async with session_factory() as session:
        async with session.begin():
            await lead_service.set_lead_status(
                session=session,
                lead_id=lead_id,
                status=ContactStatus.CALLING,
            )

    logger.info(
        "SIP participant joined, lead set to CALLING",
        extra={"room_name": room_name, "lead_id": str(lead_id)},
    )
