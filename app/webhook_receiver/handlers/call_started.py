# app/webhook_receiver/handlers/call_started.py
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.dashboard_api.websocket import broadcast
from app.models.contact import ContactStatus
from app.webhook_receiver.schemas.call_started import CallStartedPayload
from app.webhook_receiver.services import call_log_service, lead_service

logger = logging.getLogger(__name__)


async def handle_call_started(
    payload: CallStartedPayload,
    session_factory: async_sessionmaker,
) -> None:
    retell_call_id = payload.call_id

    start_time = datetime.now(tz=timezone.utc)
    if payload.start_timestamp is not None:
        start_time = datetime.fromtimestamp(payload.start_timestamp / 1000, tz=timezone.utc)

    lead_id: uuid.UUID | None = None
    if payload.metadata:
        raw_id = payload.metadata.get("lead_id")
        if raw_id:
            try:
                lead_id = uuid.UUID(raw_id)
            except ValueError:
                logger.warning(
                    "Invalid lead_id in metadata — proceeding without lead_id",
                    extra={"raw_lead_id": raw_id, "retell_call_id": retell_call_id},
                )

    try:
        async with session_factory() as session:
            async with session.begin():
                call = await call_log_service.upsert_call_log(
                    session=session,
                    retell_call_id=retell_call_id,
                    start_time=start_time,
                    lead_id=lead_id,
                )
                await lead_service.set_lead_status(
                    session=session,
                    lead_id=call.lead_id,
                    status=ContactStatus.CALLING,
                )
    except ValueError as exc:
        logger.warning(
            "Cannot record call_started — no lead_id available",
            extra={"retell_call_id": retell_call_id, "error": str(exc)},
        )
        return

    logger.info("Handled call_started", extra={"retell_call_id": retell_call_id})
    await broadcast({
        "event": "call_started",
        "call_id": retell_call_id,
        "payload": {"from_number": payload.from_number},
    })
