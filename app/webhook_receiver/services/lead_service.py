# app/webhook_receiver/services/lead_service.py
import logging
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact, ContactStatus

logger = logging.getLogger(__name__)


async def set_lead_status(
    session: AsyncSession,
    lead_id: UUID,
    status: ContactStatus,
) -> None:
    await session.execute(
        sa.update(Contact)
        .where(Contact.id == lead_id)
        .values(status=status)
    )
    logger.info(
        "Updated lead status",
        extra={"lead_id": str(lead_id), "status": status.value},
    )
