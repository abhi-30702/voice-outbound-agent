# app/webhook_receiver/handlers/call_analyzed.py
import logging

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.settings import settings
from app.models.call import Call
from app.webhook_receiver.schemas.call_analyzed import CallAnalyzedPayload
from app.webhook_receiver.services import transcript_service, queue_service

logger = logging.getLogger(__name__)


async def handle_call_analyzed(
    payload: CallAnalyzedPayload,
    session_factory: async_sessionmaker,
) -> None:
    retell_call_id = payload.call_id
    call_uuid = None

    async with session_factory() as session:
        async with session.begin():
            result = await session.execute(
                sa.select(Call).where(Call.retell_call_id == retell_call_id)
            )
            call = result.scalar_one_or_none()

            if call is None:
                logger.warning(
                    "call_log not found for call_analyzed",
                    extra={"retell_call_id": retell_call_id},
                )
                return

            await transcript_service.create_transcript(
                session=session,
                call_id=call.id,
                raw_transcript=payload.transcript,
            )
            call_uuid = call.id

    # call_uuid is set inside the session block before we get here
    # (early return handles the not-found case)
    await queue_service.enqueue_analysis(
        redis_url=settings.REDIS_URL,
        call_id=call_uuid,
    )
    logger.info("Processed call_analyzed event", extra={"retell_call_id": retell_call_id})
