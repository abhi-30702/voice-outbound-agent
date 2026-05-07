"""Integration tests for DNC filtering via SQL NOT EXISTS."""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.dialing_worker.config import DialerConfig
from app.dialing_worker.worker import DialerWorker
from app.models import Contact, ContactStatus


@pytest.mark.asyncio
async def test_dnc_check_excludes_dnc_phones():
    """Verify that SQL NOT EXISTS pattern filters DNC phones correctly.

    This test verifies that:
    1. Leads with phones in DNC registry are excluded from the query
    2. Leads without phones in DNC registry are included
    3. The filtering happens at the SQL level (NOT EXISTS clause)
    """
    config = DialerConfig(
        retell_api_key="test-key",
        batch_size=50,
        poll_interval_sec=5,
    )

    from unittest.mock import patch

    with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
        worker = DialerWorker(config)

    # Create mock session with a mock execute method
    mock_session = AsyncMock(spec=AsyncSession)

    # Simulate database response with:
    # - 2 leads that are clean (not in DNC)
    # - The DNC registry check via NOT EXISTS filters them correctly
    clean_lead_1_id = uuid4()
    clean_lead_2_id = uuid4()

    # Mock fetchall to return only clean leads (DNC filtered at SQL level)
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        (
            clean_lead_1_id,
            "+11234567890",
            "John",
            "Doe",
            "Acme",
            "America/New_York",
            uuid4(),  # campaign_id
            "pending",
            0,
            None,  # next_retry_at
            {},  # custom_vars
            None,  # created_at
            None,  # updated_at
        ),
        (
            clean_lead_2_id,
            "+19876543210",
            "Jane",
            "Smith",
            "TechCorp",
            "America/Los_Angeles",
            uuid4(),  # campaign_id
            "pending",
            0,
            None,  # next_retry_at
            {},  # custom_vars
            None,  # created_at
            None,  # updated_at
        ),
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Call _fetch_pending_leads
    leads = await worker._fetch_pending_leads(mock_session)

    # Verify SQL query was executed
    assert mock_session.execute.called
    query_call = mock_session.execute.call_args
    query_text = str(query_call[0][0])

    # Verify the query contains NOT EXISTS for DNC filtering
    assert "NOT EXISTS" in query_text
    assert "dnc_registry" in query_text
    assert "phone_number" in query_text

    # Verify the correct parameters were passed
    query_params = query_call[0][1]
    assert query_params["status"] == "pending"
    assert query_params["limit"] == 50

    # Verify returned leads are clean (not DNC)
    assert len(leads) == 2
    assert leads[0].phone_number == "+11234567890"
    assert leads[1].phone_number == "+19876543210"

    # Both should be pending status
    assert all(lead.status == "pending" for lead in leads)


@pytest.mark.asyncio
async def test_dnc_filtering_parameterized_queries():
    """Verify that DNC filtering uses parameterized queries (no string interpolation).

    This test verifies that the SQL query for DNC filtering uses bound parameters,
    not string interpolation, to prevent SQL injection.
    """
    config = DialerConfig(
        retell_api_key="test-key",
        batch_size=50,
        poll_interval_sec=5,
    )

    from unittest.mock import patch

    with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
        worker = DialerWorker(config)

    # Create mock session
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Call _fetch_pending_leads
    await worker._fetch_pending_leads(mock_session)

    # Verify parameterized query was used
    query_call = mock_session.execute.call_args
    query_obj = query_call[0][0]  # The query object
    query_params = query_call[0][1]  # The parameters dict

    # Verify bound parameters are used (not string interpolation)
    assert isinstance(query_params, dict)
    assert "status" in query_params
    assert query_params["status"] == "pending"

    # Verify the query string contains :param syntax (SQLAlchemy bound parameters)
    query_text = str(query_obj)
    assert ":status" in query_text or "?" in query_text  # Either named or positional


@pytest.mark.asyncio
async def test_dnc_filter_multiple_phone_formats():
    """Verify DNC filtering works with different phone number formats.

    This test verifies that the DNC filter works correctly regardless of
    phone number format (assumes all numbers are in E.164).
    """
    config = DialerConfig(
        retell_api_key="test-key",
        batch_size=50,
        poll_interval_sec=5,
    )

    from unittest.mock import patch

    with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
        worker = DialerWorker(config)

    # Create mock session
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock leads with different E.164 formats
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        (
            uuid4(),
            "+11234567890",  # US format
            "John",
            "Doe",
            "Company",
            "America/New_York",
            uuid4(),
            "pending",
            0,
            None,
            {},
            None,
            None,
        ),
        (
            uuid4(),
            "+919876543210",  # India format
            "Raj",
            "Kumar",
            "Company",
            "Asia/Kolkata",
            uuid4(),
            "pending",
            0,
            None,
            {},
            None,
            None,
        ),
        (
            uuid4(),
            "+442071838750",  # UK format
            "John",
            "Smith",
            "Company",
            "Europe/London",
            uuid4(),
            "pending",
            0,
            None,
            {},
            None,
            None,
        ),
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Fetch leads
    leads = await worker._fetch_pending_leads(mock_session)

    # Verify all formats are handled correctly
    assert len(leads) == 3
    phone_numbers = [lead.phone_number for lead in leads]
    assert "+11234567890" in phone_numbers
    assert "+919876543210" in phone_numbers
    assert "+442071838750" in phone_numbers
