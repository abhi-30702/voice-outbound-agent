# app/webhook_receiver/services/transcript_service.py
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transcript import Transcript

logger = logging.getLogger(__name__)


async def create_transcript(
    session: AsyncSession,
    call_id: UUID,
    raw_transcript: str | None,
) -> Transcript:
    transcript = Transcript(
        call_id=call_id,
        raw_transcript=raw_transcript,
    )
    session.add(transcript)
    await session.flush()
    logger.info("Created call_transcript", extra={"call_id": str(call_id)})
    return transcript
