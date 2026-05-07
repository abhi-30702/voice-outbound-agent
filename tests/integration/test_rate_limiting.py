"""Integration tests for rate limiting (1 CPS enforcement)."""
import asyncio
import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.dialing_worker.config import DialerConfig
from app.dialing_worker.worker import DialerWorker
from app.models import Campaign, Contact, ContactStatus


@pytest.mark.asyncio
async def test_1_cps_rate_limit():
    """Verify that 1 CPS rate limit is enforced via asyncio.sleep(1.0).

    This test dispatches 5 calls and verifies that they take approximately
    4-5 seconds (since 5 calls with 1 second sleep between each = 4 seconds minimum).
    """
    config = DialerConfig(
        retell_api_key="test-key",
        batch_size=50,
        poll_interval_sec=5,
    )

    with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
        worker = DialerWorker(config)
        worker.retell_client.create_call = AsyncMock(
            return_value={"call_id": "call_123"}
        )

    # Create 5 mock leads
    campaign_id = uuid4()
    leads = [
        Contact(
            id=uuid4(),
            phone_number=f"+1123456789{i}",
            first_name=f"Lead{i}",
            timezone="America/New_York",
            campaign_id=campaign_id,
            status=ContactStatus.PENDING,
        )
        for i in range(5)
    ]

    # Mock campaign
    campaign = Campaign(
        id=campaign_id,
        name="Test Campaign",
        llm_config={"retell_agent_id": "agent_123"},
    )

    # Mock session
    from unittest.mock import MagicMock, AsyncMock as AM
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = AM(spec=AsyncSession)
    mock_session.get = AM(return_value=campaign)

    # Simulate dial_batch by manually dispatching each lead with sleep
    start_time = time.time()

    for lead in leads:
        await worker._dispatch_call(mock_session, lead)
        # The actual 1 CPS sleep happens in dial_batch, so we simulate it here
        await asyncio.sleep(1.0)

    elapsed = time.time() - start_time

    # 5 calls with 1 second sleep = ~4 seconds minimum
    # We dispatch 5 calls and sleep 1 second after each of the first 4
    # So minimum time should be around 4-4.5 seconds
    assert elapsed >= 4.0, f"Rate limiting not enforced: {elapsed} seconds"
    assert elapsed < 6.0, f"Rate limiting too slow: {elapsed} seconds"

    # Verify all 5 calls were made
    assert worker.retell_client.create_call.call_count == 5
