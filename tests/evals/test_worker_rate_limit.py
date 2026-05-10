"""Rate-limit eval: 10 leads dispatched → elapsed ≥ 9.0s (asyncio.sleep(1.0) enforced).

No database required — all DB calls are mocked.
Run: pytest tests/evals/test_worker_rate_limit.py -v
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.dialing_worker.config import DialerConfig
from app.dialing_worker.worker import DialerWorker
from app.models import Contact, ContactStatus

LEAD_COUNT = 10


@pytest.mark.asyncio
async def test_1_cps_enforced_over_10_leads():
    """dial_batch with 10 leads must take ≥ 9.0s and call create_call exactly 10 times."""
    config = DialerConfig(retell_api_key="test-key", batch_size=50)

    with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
        worker = DialerWorker(config)

    worker.retell_client.create_call = AsyncMock(return_value={"call_id": "c1"})

    campaign_id = uuid4()
    leads = [
        Contact(
            id=uuid4(),
            phone_number=f"+1555{str(i).zfill(7)}",
            first_name=f"Lead{i}",
            timezone="America/New_York",
            campaign_id=campaign_id,
            status=ContactStatus.PENDING,
        )
        for i in range(LEAD_COUNT)
    ]

    # _fetch_pending_leads uses session.execute(text(...)).fetchall()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        (l.id, l.phone_number, l.first_name, None, None,
         l.timezone, l.campaign_id, "pending", 0, None, None, None, None)
        for l in leads
    ]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    # _dispatch_call uses session.get(Campaign, campaign_id)
    mock_session.get = AsyncMock(return_value=MagicMock(
        name="Test Campaign",
        llm_config={"retell_agent_id": "agent_eval"},
    ))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    worker.session_factory = MagicMock(return_value=cm)

    with patch("app.dialing_worker.worker.is_within_calling_hours", return_value=True):
        start = time.monotonic()
        await worker.dial_batch()
        elapsed = time.monotonic() - start

    assert worker.retell_client.create_call.call_count == LEAD_COUNT, (
        f"Expected {LEAD_COUNT} calls, got {worker.retell_client.create_call.call_count}"
    )
    assert elapsed >= 9.0, f"1 CPS not enforced: elapsed={elapsed:.2f}s for {LEAD_COUNT} leads"
    assert elapsed < 15.0, f"Worker too slow: elapsed={elapsed:.2f}s"
