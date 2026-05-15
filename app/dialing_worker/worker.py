import asyncio
import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.dialing_worker.config import DialerConfig
from app.dialing_worker.errors import DialerError
from app.dialing_worker.livekit_client import LiveKitClient
from app.dialing_worker.phone_utils import is_e164
from app.dialing_worker.timezone_utils import is_within_calling_hours
from app.models import Contact, ContactStatus, Campaign, Call

logger = logging.getLogger(__name__)


class DialerWorker:
    """RQ-based dialing worker for outbound voice calls via LiveKit.

    Enforces:
    - 1 CPS (call per second) rate limit via asyncio.sleep(1.0)
    - Timezone-aware calling hours (8am-9pm local time)
    - DNC filtering via SQL NOT EXISTS
    - E.164 phone validation
    - Exponential backoff on retriable errors
    """

    def __init__(self, config: DialerConfig) -> None:
        self.config = config
        self.livekit_client = LiveKitClient(
            url=config.livekit_url,
            api_key=config.livekit_api_key,
            api_secret=config.livekit_api_secret,
            sip_trunk_id=config.livekit_sip_trunk_id,
        )
        self._running = False

    async def initialize(self) -> None:
        self.session_factory = await get_session_factory()
        logger.info("DialerWorker initialized")

    async def run(self) -> None:
        await self.initialize()
        self._running = True
        logger.info("DialerWorker loop started")
        try:
            while self._running:
                await self.dial_batch()
                await asyncio.sleep(self.config.poll_interval_sec)
        except asyncio.CancelledError:
            logger.info("DialerWorker loop cancelled")
        except Exception as exc:
            logger.error("DialerWorker loop error: %s", exc, exc_info=True)
        finally:
            await self.livekit_client.close()

    async def dial_batch(self) -> None:
        async with self.session_factory() as session:
            leads = await self._fetch_pending_leads(session)
            logger.info("Fetched %d pending leads", len(leads))

            dialable = [
                lead for lead in leads
                if is_within_calling_hours(
                    lead.timezone,
                    start_hour=self.config.start_hour,
                    end_hour=self.config.end_hour,
                )
            ]
            logger.info("Timezone filter: %d dialable leads", len(dialable))

            for lead in dialable:
                try:
                    await self._dispatch_call(session, lead)
                    await asyncio.sleep(1.0)  # enforce 1 CPS
                except Exception as exc:
                    logger.error("Error dispatching call for lead %s: %s", lead.id, exc)

    async def _fetch_pending_leads(self, session: AsyncSession) -> list[Contact]:
        query = text("""
            SELECT l.id, l.phone_number, l.first_name, l.last_name, l.company,
                   l.timezone, l.campaign_id, l.status, l.retry_count,
                   l.next_retry_at, l.custom_vars, l.created_at, l.updated_at
            FROM agent_operations.leads l
            WHERE l.status = :status
              AND (l.next_retry_at IS NULL OR l.next_retry_at <= :now)
              AND NOT EXISTS (
                  SELECT 1 FROM agent_operations.dnc_registry d
                  WHERE d.phone_number = l.phone_number
              )
            ORDER BY l.created_at ASC
            LIMIT :limit
        """)
        result = await session.execute(
            query,
            {"status": ContactStatus.PENDING.name, "now": datetime.utcnow(), "limit": self.config.batch_size},
        )
        leads = []
        for row in result.fetchall():
            leads.append(Contact(
                id=row[0], phone_number=row[1], first_name=row[2], last_name=row[3],
                company=row[4], timezone=row[5], campaign_id=row[6], status=row[7],
                retry_count=row[8], next_retry_at=row[9], custom_vars=row[10],
            ))
        return leads

    async def _dispatch_call(self, session: AsyncSession, lead: Contact) -> None:
        if not is_e164(lead.phone_number):
            logger.error("Invalid phone format for lead %s: %s", lead.id, lead.phone_number)
            return

        campaign = await session.get(Campaign, lead.campaign_id)
        if not campaign:
            logger.error("Campaign %s not found for lead %s", lead.campaign_id, lead.id)
            return

        room_name = f"call-{lead.id}"
        metadata = {
            "lead_id": str(lead.id),
            "campaign_id": str(lead.campaign_id),
            "first_name": lead.first_name or "",
            "last_name": lead.last_name or "",
        }

        try:
            await self.livekit_client.create_room(room_name, metadata)
            await self.livekit_client.create_sip_participant(room_name, lead.phone_number)

            call_log = Call(lead_id=lead.id, retell_call_id=room_name)
            session.add(call_log)

            lead.status = ContactStatus.CALLING
            await session.merge(lead)
            await session.commit()

            logger.info("Call dispatched for lead %s, room=%s", lead.id, room_name)

        except DialerError as exc:
            await self._handle_dialer_error(session, lead, exc)

    async def _handle_dialer_error(
        self, session: AsyncSession, lead: Contact, error: DialerError
    ) -> None:
        if error.retriable:
            lead.retry_count += 1
            backoff_sec = min(2 ** lead.retry_count, 60)
            lead.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_sec)
            lead.status = ContactStatus.PENDING
            logger.info(
                "Retriable error for lead %s, retry_count=%d, next_retry_at=%s: %s",
                lead.id, lead.retry_count, lead.next_retry_at, error.message,
            )
        else:
            lead.status = ContactStatus.FAILED
            logger.warning("Permanent error for lead %s: %s", lead.id, error.message)

        await session.merge(lead)
        await session.commit()

    def stop(self) -> None:
        self._running = False
        logger.info("DialerWorker stop requested")
