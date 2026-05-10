# app/webhook_receiver/handlers/transcript_updated.py
import logging

from app.dashboard_api.websocket import broadcast
from app.webhook_receiver.schemas.transcript_updated import TranscriptUpdatedPayload

logger = logging.getLogger(__name__)


async def handle_transcript_updated(payload: TranscriptUpdatedPayload) -> None:
    await broadcast({
        "event": "transcript_updated",
        "call_id": payload.call_id,
        "payload": {"transcript": payload.transcript},
    })
    logger.debug(
        "Broadcast transcript_updated",
        extra={"retell_call_id": payload.call_id},
    )
