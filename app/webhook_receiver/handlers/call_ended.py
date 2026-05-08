# app/webhook_receiver/handlers/call_ended.py
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.contact import ContactStatus
from app.webhook_receiver.config import FAILED_DISCONNECT_REASONS
from app.webhook_receiver.schemas.call_ended import CallEndedPayload
from app.webhook_receiver.services import call_log_service, lead_service

logger = logging.getLogger(__name__)


async def handle_call_ended(
    payload: CallEndedPayload,
    session_factory: async_sessionmaker,
) -> None:
    retell_call_id = payload.call_id

    end_time = datetime.now(tz=timezone.utc)
    if payload.end_timestamp is not None:
        end_time = datetime.fromtimestamp(payload.end_timestamp / 1000, tz=timezone.utc)

    duration_sec: int | None = None
    if payload.duration_ms is not None:
        duration_sec = payload.duration_ms // 1000

    lead_status = (
        ContactStatus.FAILED
        if payload.disconnect_reason in FAILED_DISCONNECT_REASONS
        else ContactStatus.COMPLETED
    )

    async with session_factory() as session:
        async with session.begin():
            call = await call_log_service.update_call_end(
                session=session,
                retell_call_id=retell_call_id,
                end_time=end_time,
                duration_sec=duration_sec,
                disconnect_reason=payload.disconnect_reason,
                recording_url=payload.recording_url,
            )
            if call is not None and call.lead_id is not None:
                await lead_service.set_lead_status(
                    session=session,
                    lead_id=call.lead_id,
                    status=lead_status,
                )

    logger.info(
        "Handled call_ended",
        extra={"retell_call_id": retell_call_id, "disconnect_reason": payload.disconnect_reason},
    )
