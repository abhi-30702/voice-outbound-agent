# app/webhook_receiver/services/call_log_service.py
import logging
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call, CallStatus

logger = logging.getLogger(__name__)


async def upsert_call_log(
    session: AsyncSession,
    retell_call_id: str,
    start_time: datetime,
    lead_id: UUID | None = None,
) -> Call:
    result = await session.execute(
        sa.select(Call).where(Call.retell_call_id == retell_call_id)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.start_time = start_time
        await session.flush()
        logger.info("Updated call_log start_time", extra={"retell_call_id": retell_call_id})
        return existing

    if lead_id is None:
        raise ValueError(f"Cannot create call_log without lead_id for retell_call_id={retell_call_id}")

    call = Call(
        retell_call_id=retell_call_id,
        lead_id=lead_id,
        start_time=start_time,
        status=CallStatus.CALLING,
    )
    session.add(call)
    await session.flush()
    logger.info("Created call_log", extra={"retell_call_id": retell_call_id})
    return call


async def update_call_end(
    session: AsyncSession,
    retell_call_id: str,
    end_time: datetime,
    duration_sec: int | None,
    disconnect_reason: str | None,
    recording_url: str | None,
) -> Call | None:
    result = await session.execute(
        sa.select(Call).where(Call.retell_call_id == retell_call_id)
    )
    call = result.scalar_one_or_none()

    if call is None:
        logger.warning("call_log not found", extra={"retell_call_id": retell_call_id})
        return None

    call.end_time = end_time
    call.duration_sec = duration_sec
    call.disconnect_reason = disconnect_reason
    call.recording_url = recording_url
    await session.flush()
    return call
