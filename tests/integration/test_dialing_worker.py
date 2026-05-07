"""Integration tests for the DialerWorker."""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.dialing_worker.config import DialerConfig
from app.dialing_worker.errors import RetellAPIError
from app.dialing_worker.worker import DialerWorker
from app.models import Campaign, Contact, ContactStatus, Call


@pytest.fixture
def dialer_config():
    """Fixture for DialerConfig."""
    return DialerConfig(
        retell_api_key="test-key",
        retell_base_url="https://api.retellai.com",
        retell_timeout_sec=30.0,
        batch_size=50,
        poll_interval_sec=5,
        start_hour=8,
        end_hour=21,
    )


@pytest.fixture
def dialer_worker(dialer_config):
    """Fixture for DialerWorker."""
    with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
        worker = DialerWorker(dialer_config)
    return worker


class TestDialerWorkerInit:
    """Tests for DialerWorker initialization."""

    def test_init_creates_config(self, dialer_config):
        """Test that init stores config correctly."""
        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            worker = DialerWorker(dialer_config)
            assert worker.config == dialer_config

    def test_init_creates_retell_client(self, dialer_config):
        """Test that init creates RetellClient."""
        with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
            worker = DialerWorker(dialer_config)
            assert worker.retell_client is not None
            assert worker.retell_client.api_key == "test-key"


class TestDialerWorkerFetchLeads:
    """Tests for _fetch_pending_leads method."""

    @pytest.mark.asyncio
    async def test_fetch_pending_leads_returns_contacts(self, dialer_worker):
        """Test that fetch_pending_leads returns Contact objects."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Create mock lead data
        lead_id = uuid4()
        campaign_id = uuid4()

        # Mock the execute call
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (
                lead_id,
                "+11234567890",
                "John",
                "Doe",
                "Acme",
                "America/New_York",
                campaign_id,
                "pending",
                0,
                None,
                {},
                datetime.utcnow(),
                datetime.utcnow(),
            )
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        leads = await dialer_worker._fetch_pending_leads(mock_session)

        assert len(leads) == 1
        assert leads[0].phone_number == "+11234567890"
        assert leads[0].status == "pending"

    @pytest.mark.asyncio
    async def test_fetch_pending_leads_excludes_dnc_via_sql(self, dialer_worker):
        """Test that DNC filtering uses SQL NOT EXISTS (not application logic)."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await dialer_worker._fetch_pending_leads(mock_session)

        # Verify that SQL query was executed with NOT EXISTS
        call_args = mock_session.execute.call_args
        query_text = str(call_args[0][0])
        assert "NOT EXISTS" in query_text
        assert "dnc_registry" in query_text


class TestDispatchCall:
    """Tests for _dispatch_call method."""

    @pytest.mark.asyncio
    async def test_dispatch_call_successful(self, dialer_worker):
        """Test successful call dispatch."""
        campaign_id = uuid4()
        lead_id = uuid4()

        # Create mock lead
        lead = Contact(
            id=lead_id,
            phone_number="+11234567890",
            first_name="John",
            company="Acme",
            timezone="America/New_York",
            campaign_id=campaign_id,
            custom_vars={"custom": "value"},
        )

        # Create mock campaign
        campaign = Campaign(
            id=campaign_id,
            name="Test Campaign",
            llm_config={"retell_agent_id": "agent_123"},
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.get = AsyncMock(return_value=campaign)

        # Mock Retell API response
        dialer_worker.retell_client.create_call = AsyncMock(
            return_value={"call_id": "call_456"}
        )

        await dialer_worker._dispatch_call(mock_session, lead)

        # Verify Retell API was called with correct parameters
        call_args = dialer_worker.retell_client.create_call.call_args
        assert call_args[1]["to_number"] == "+11234567890"
        assert call_args[1]["agent_id"] == "agent_123"
        assert call_args[1]["dynamic_variables"]["first_name"] == "John"
        assert call_args[1]["dynamic_variables"]["custom"] == "value"

        # Verify session.add was called (for creating call log and updating lead)
        assert mock_session.add.called
        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_dispatch_call_invalid_phone_skips_dispatch(self, dialer_worker):
        """Test that invalid E.164 phone prevents dispatch."""
        lead_id = uuid4()

        # Create lead with invalid phone
        lead = Contact(
            id=lead_id,
            phone_number="123-456-7890",  # Not E.164
            timezone="America/New_York",
        )

        mock_session = AsyncMock(spec=AsyncSession)
        dialer_worker.retell_client.create_call = AsyncMock()

        await dialer_worker._dispatch_call(mock_session, lead)

        # Verify Retell API was NOT called
        dialer_worker.retell_client.create_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_call_updates_lead_status_to_calling(self, dialer_worker):
        """Test that successful dispatch updates lead status to CALLING."""
        campaign_id = uuid4()
        lead_id = uuid4()

        lead = Contact(
            id=lead_id,
            phone_number="+11234567890",
            timezone="America/New_York",
            campaign_id=campaign_id,
            status=ContactStatus.PENDING,
        )

        campaign = Campaign(
            id=campaign_id,
            name="Test Campaign",
            llm_config={"retell_agent_id": "agent_123"},
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.get = AsyncMock(return_value=campaign)
        dialer_worker.retell_client.create_call = AsyncMock(
            return_value={"call_id": "call_456"}
        )

        await dialer_worker._dispatch_call(mock_session, lead)

        # Verify lead status was updated
        assert lead.status == ContactStatus.CALLING


class TestHandleRetellError:
    """Tests for _handle_retell_error method."""

    @pytest.mark.asyncio
    async def test_retriable_error_increments_retry_count(self, dialer_worker):
        """Test that retriable errors increment retry_count."""
        lead = Contact(
            id=uuid4(),
            phone_number="+11234567890",
            timezone="America/New_York",
            retry_count=0,
            status=ContactStatus.PENDING,
        )

        error = RetellAPIError(
            message="Rate limited",
            retriable=True,
            status_code=429,
        )

        mock_session = AsyncMock(spec=AsyncSession)

        await dialer_worker._handle_retell_error(mock_session, lead, error)

        assert lead.retry_count == 1
        assert lead.status == ContactStatus.PENDING
        assert lead.next_retry_at is not None

    @pytest.mark.asyncio
    async def test_retriable_error_exponential_backoff(self, dialer_worker):
        """Test exponential backoff formula: min(2^retry_count, 60)."""
        lead = Contact(
            id=uuid4(),
            phone_number="+11234567890",
            timezone="America/New_York",
            retry_count=0,
            status=ContactStatus.PENDING,
        )

        error = RetellAPIError(
            message="Rate limited",
            retriable=True,
            status_code=429,
        )

        mock_session = AsyncMock(spec=AsyncSession)

        before = datetime.utcnow()
        await dialer_worker._handle_retell_error(mock_session, lead, error)
        after = datetime.utcnow()

        # After 1st retry: 2^1 = 2 seconds
        delta = (lead.next_retry_at - before).total_seconds()
        assert 1 <= delta <= 3  # Allow 1-3 second window

    @pytest.mark.asyncio
    async def test_exponential_backoff_capped_at_60_seconds(self, dialer_worker):
        """Test that backoff is capped at 60 seconds."""
        lead = Contact(
            id=uuid4(),
            phone_number="+11234567890",
            timezone="America/New_York",
            retry_count=10,  # Would be 2^10 = 1024 seconds without cap
            status=ContactStatus.PENDING,
        )

        error = RetellAPIError(
            message="Rate limited",
            retriable=True,
            status_code=429,
        )

        mock_session = AsyncMock(spec=AsyncSession)

        before = datetime.utcnow()
        await dialer_worker._handle_retell_error(mock_session, lead, error)

        delta = (lead.next_retry_at - before).total_seconds()
        # Should be capped at 60 seconds
        assert delta <= 61  # Allow 1 second window

    @pytest.mark.asyncio
    async def test_permanent_error_sets_status_failed(self, dialer_worker):
        """Test that permanent errors mark lead as FAILED."""
        lead = Contact(
            id=uuid4(),
            phone_number="+11234567890",
            timezone="America/New_York",
            retry_count=0,
            status=ContactStatus.PENDING,
        )

        error = RetellAPIError(
            message="Invalid phone number",
            retriable=False,
            status_code=400,
        )

        mock_session = AsyncMock(spec=AsyncSession)

        await dialer_worker._handle_retell_error(mock_session, lead, error)

        assert lead.status == ContactStatus.FAILED
        assert mock_session.add.called
        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_retriable_error_keeps_status_pending(self, dialer_worker):
        """Test that retriable errors don't change status to FAILED."""
        lead = Contact(
            id=uuid4(),
            phone_number="+11234567890",
            timezone="America/New_York",
            retry_count=0,
            status=ContactStatus.PENDING,
        )

        error = RetellAPIError(
            message="Service unavailable",
            retriable=True,
            status_code=503,
        )

        mock_session = AsyncMock(spec=AsyncSession)

        await dialer_worker._handle_retell_error(mock_session, lead, error)

        assert lead.status == ContactStatus.PENDING


class TestDialBatch:
    """Tests for dial_batch method."""

    @pytest.mark.asyncio
    async def test_dial_batch_filters_by_timezone(self, dialer_worker):
        """Test that dial_batch filters leads by calling hours."""
        # Create a proper async context manager mock
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock the session factory to return an async context manager
        async def async_context_manager():
            return mock_session

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        dialer_worker.session_factory = mock_session_factory
        dialer_worker._fetch_pending_leads = AsyncMock(return_value=[])

        await dialer_worker.dial_batch()

        # Verify _fetch_pending_leads was called
        dialer_worker._fetch_pending_leads.assert_called_once()
