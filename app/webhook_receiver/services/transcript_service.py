# app/webhook_receiver/services/transcript_service.py
import logging
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transcript import Transcript

logger = logging.getLogger(__name__)


async def create_transcript(
    session: AsyncSession,
    call_id: UUID,
    raw_transcript: str | None,
) -> Transcript:
    result = await session.execute(sa.select(Transcript).where(Transcript.call_id == call_id))
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.raw_transcript = raw_transcript
        await session.flush()
        logger.info("Updated existing call_transcript", extra={"call_id": str(call_id)})
        return existing
    transcript = Transcript(
        call_id=call_id,
        raw_transcript=raw_transcript,
    )
    session.add(transcript)
    await session.flush()
    logger.info("Created call_transcript", extra={"call_id": str(call_id)})
    return transcript
