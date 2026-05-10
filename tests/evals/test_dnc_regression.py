"""DNC regression: 90 clean + 10 DNC leads → _fetch_pending_leads returns 90, 0 from DNC.

Requires a live PostgreSQL instance at DATABASE_URL.
Run: pytest tests/evals/test_dnc_regression.py -v
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.dialing_worker.config import DialerConfig
from app.dialing_worker.worker import DialerWorker
from app.models import Contact, ContactStatus, DNCEntry, DNCSource


@pytest.mark.asyncio
async def test_zero_dnc_leads_dispatched(db_session):
    """SQL NOT EXISTS filters all DNC-listed phones; 90 clean leads returned."""
    past = datetime.utcnow() - timedelta(minutes=5)

    clean_phones = [f"+1555{str(i).zfill(7)}" for i in range(90)]
    dnc_phones = [f"+1999{str(i).zfill(7)}" for i in range(10)]

    for phone in clean_phones + dnc_phones:
        db_session.add(Contact(
            phone_number=phone,
            first_name="Test",
            timezone="America/New_York",
            status=ContactStatus.PENDING,
            next_retry_at=past,
        ))

    for phone in dnc_phones:
        db_session.add(DNCEntry(
            phone_number=phone,
            source=DNCSource.MANUAL,
        ))

    await db_session.flush()   # write within SAVEPOINT — never committed

    with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
        worker = DialerWorker(DialerConfig(retell_api_key="test", batch_size=200))

    result = await worker._fetch_pending_leads(db_session)

    result_phones = {c.phone_number for c in result}
    dnc_set = set(dnc_phones)

    assert len(result) == 90, f"Expected 90 leads, got {len(result)}"
    leaked = result_phones & dnc_set
    assert not leaked, f"DNC leads leaked into results: {leaked}"
