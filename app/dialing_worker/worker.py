"""Core RQ worker for outbound dialing."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.dialing_worker.config import DialerConfig
from app.dialing_worker.errors import RetellAPIError
from app.dialing_worker.phone_utils import is_e164
from app.dialing_worker.retell_client import RetellClient
from app.dialing_worker.timezone_utils import is_within_calling_hours
from app.models import Contact, ContactStatus, Campaign, Call

logger = logging.getLogger(__name__)


class DialerWorker:
    """RQ-based dialing worker for outbound voice calls.

    Enforces:
    - 1 CPS (call per second) rate limit via asyncio.sleep(1.0)
    - Timezone-aware calling hours (8am-9pm local time)
    - DNC filtering via SQL NOT EXISTS
    - E.164 phone validation
    - Exponential backoff on retriable errors
    """

    def __init__(self, config: DialerConfig):
        """Initialize the dialing worker.

        Args:
            config: Dialer configuration object
        """
        self.config = config
        self.retell_client = RetellClient(
            api_key=config.retell_api_key,
            base_url=config.retell_base_url,
            timeout=config.retell_timeout_sec,
        )
        self._running = False

    async def initialize(self) -> None:
        """Initialize worker resources (session factory, etc.)."""
        self.session_factory = await get_session_factory()
        logger.info("DialerWorker initialized")

    async def run(self) -> None:
        """Main worker loop: continuously fetch and dial leads."""
        await self.initialize()
        self._running = True
        logger.info("DialerWorker loop started")

        try:
            while self._running:
                await self.dial_batch()
                # Poll interval between batches
                await asyncio.sleep(self.config.poll_interval_sec)
        except asyncio.CancelledError:
            logger.info("DialerWorker loop cancelled")
        except Exception as e:
            logger.error(f"DialerWorker loop error: {e}", exc_info=True)
        finally:
            await self.retell_client.close()

    async def dial_batch(self) -> None:
        """Fetch pending leads and dial them with 1 CPS rate limit."""
        async with self.session_factory() as session:
            # Fetch pending leads (max 50) excluding DNC
            leads = await self._fetch_pending_leads(session)
            logger.info(f"Fetched {len(leads)} pending leads")

            # Filter by timezone (8am-9pm local time)
            dialable_leads = [
                lead
                for lead in leads
                if is_within_calling_hours(
                    lead.timezone,
                    start_hour=self.config.start_hour,
                    end_hour=self.config.end_hour,
                )
            ]
            logger.info(f"Timezone filter: {len(dialable_leads)} dialable leads")

            # Dial each lead with 1 CPS rate limit
            for lead in dialable_leads:
                try:
                    await self._dispatch_call(session, lead)
                    # Enforce 1 CPS: sleep 1 second before next call
                    await asyncio.sleep(1.0)
                except Exception as e:
                    logger.error(f"Error dispatching call for lead {lead.id}: {e}")

    async def _fetch_pending_leads(self, session: AsyncSession) -> list[Contact]:
        """Fetch pending leads not in DNC registry.

        Uses SQL NOT EXISTS for DNC filtering (per CLAUDE.md requirements).

        Args:
            session: AsyncSession for database access

        Returns:
            List of Contact objects ready to dial
        """
        query = text("""
            SELECT l.id, l.phone_number, l.first_name, l.last_name, l.company,
                   l.timezone, l.campaign_id, l.status, l.retry_count,
                   l.next_retry_at, l.custom_vars, l.created_at, l.updated_at
            FROM agent_operations.leads l
            WHERE l.status = :status
              AND l.next_retry_at <= :now
              AND NOT EXISTS (
                  SELECT 1 FROM agent_operations.dnc_registry d
                  WHERE d.phone_number = l.phone_number
              )
            ORDER BY l.created_at ASC
            LIMIT :limit
        """)

        now = datetime.utcnow()
        result = await session.execute(
            query,
            {
                "status": ContactStatus.PENDING.value,
                "now": now,
                "limit": self.config.batch_size,
            },
        )

        rows = result.fetchall()
        leads = []
        for row in rows:
            # Map row to Contact object (simplified for demo)
            lead = Contact(
                id=row[0],
                phone_number=row[1],
                first_name=row[2],
                last_name=row[3],
                company=row[4],
                timezone=row[5],
                campaign_id=row[6],
                status=row[7],
                retry_count=row[8],
                next_retry_at=row[9],
                custom_vars=row[10],
            )
            leads.append(lead)

        return leads

    async def _dispatch_call(self, session: AsyncSession, lead: Contact) -> None:
        """Dispatch a single call via Retell AI.

        Args:
            session: AsyncSession for database access
            lead: Contact object to call

        Raises:
            Exception: Any unhandled error
        """
        # Validate E.164 phone number
        if not is_e164(lead.phone_number):
            logger.error(f"Invalid phone format for lead {lead.id}: {lead.phone_number}")
            return

        # Fetch campaign to get Retell agent ID and other config
        campaign = await session.get(Campaign, lead.campaign_id)
        if not campaign:
            logger.error(f"Campaign {lead.campaign_id} not found for lead {lead.id}")
            return

        # Build dynamic variables from lead data + custom vars
        dynamic_variables = {
            "first_name": lead.first_name or "",
            "company": lead.company or "",
        }
        if lead.custom_vars:
            dynamic_variables.update(lead.custom_vars)

        # Call Retell API to create the call
        try:
            response = await self.retell_client.create_call(
                to_number=lead.phone_number,
                agent_id=campaign.llm_config.get(
                    "retell_agent_id", ""
                ),  # Simplified
                dynamic_variables=dynamic_variables,
            )
            retell_call_id = response.get("call_id")

            # Create call log entry
            call_log = Call(
                lead_id=lead.id,
                retell_call_id=retell_call_id,
            )
            session.add(call_log)

            # Update lead status to CALLING
            lead.status = ContactStatus.CALLING
            session.add(lead)

            await session.commit()
            logger.info(
                f"Call dispatched for lead {lead.id}, retell_call_id={retell_call_id}"
            )

        except RetellAPIError as e:
            await self._handle_retell_error(session, lead, e)

    async def _handle_retell_error(
        self, session: AsyncSession, lead: Contact, error: RetellAPIError
    ) -> None:
        """Handle Retell API errors with exponential backoff.

        Args:
            session: AsyncSession for database access
            lead: Contact object that failed
            error: RetellAPIError raised during dispatch
        """
        if error.retriable:
            # Increment retry count and schedule next retry
            lead.retry_count += 1
            # Exponential backoff: 2^retry_count, max 60 seconds
            backoff_sec = min(2 ** lead.retry_count, 60)
            lead.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_sec)
            lead.status = ContactStatus.PENDING

            logger.info(
                f"Retriable error for lead {lead.id}, retry_count={lead.retry_count}, "
                f"next_retry_at={lead.next_retry_at}: {error.message}"
            )
        else:
            # Permanent error: mark as failed
            lead.status = ContactStatus.FAILED
            logger.warning(
                f"Permanent error for lead {lead.id}: {error.message}"
            )

        session.add(lead)
        await session.commit()

    def stop(self) -> None:
        """Stop the worker loop gracefully."""
        self._running = False
        logger.info("DialerWorker stop requested")
