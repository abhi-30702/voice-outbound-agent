# app/webhook_receiver/handlers/transcript_updated.py
import logging

from app.webhook_receiver.schemas.transcript_updated import TranscriptUpdatedPayload

logger = logging.getLogger(__name__)


async def handle_transcript_updated(payload: TranscriptUpdatedPayload) -> None:
    logger.info(
        "Received transcript_updated (no DB write — dashboard not yet built)",
        extra={"retell_call_id": payload.call_id},
    )
