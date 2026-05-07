# Design: Dialing Worker Module (Module 2)

**Date:** 2026-05-07  
**Module:** 2 (Dialing Worker)  
**Status:** Design Approved  

---

## Executive Summary

The dialing worker is a standalone RQ job that polls the PostgreSQL database for pending leads, filters by timezone and DNC registry, validates phone numbers, and dispatches calls to Retell AI at a strict 1 call-per-second rate. All DNC checks occur at the database layer (SQL NOT EXISTS), and all operations respect lead timezone constraints.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────┐
│ RQ Worker Process (long-running)             │
└──────────────────────┬──────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
    PostgreSQL    Redis Queue    Retell AI API
  (lead polling)  (job dispatch) (call dispatch)
```

**Worker Loop (pseudocode):**

```python
async def dial_batch():
    # 1. Fetch 50 pending leads (DNC-filtered in SQL)
    leads = await db.fetch("""
        SELECT l.* FROM agent_operations.leads l
        WHERE l.status = 'pending'
          AND l.next_retry_at <= NOW()
          AND NOT EXISTS (
              SELECT 1 FROM agent_operations.dnc_registry d
              WHERE d.phone_number = l.phone_number
          )
        ORDER BY l.created_at
        LIMIT 50
    """)
    
    # 2. Timezone gate (8am–9pm local time)
    dialable = [l for l in leads 
                if is_within_calling_hours(l.timezone)]
    
    # 3. Dispatch with strict 1 CPS rate limit
    for lead in dialable:
        # Validate phone
        if not is_e164(lead.phone_number):
            mark_lead_failed(lead.id)
            continue
        
        # Call Retell AI
        try:
            call_id = await retell_client.create_call(
                to_number=lead.phone_number,
                agent_id=campaign.retell_agent_id,
                dynamic_variables={
                    "first_name": lead.first_name,
                    "company": lead.company,
                    **lead.custom_vars
                }
            )
            # Update lead status
            await db.update_lead_status(lead.id, "calling")
        except RetellAPIError as e:
            # Handle retriable vs permanent errors
            handle_retell_error(lead.id, e)
        
        # Strict 1 CPS rate limit
        await asyncio.sleep(1.0)
    
    # Poll interval
    await asyncio.sleep(5)
```

---

## 2. Module Structure

### File Organization

```
app/dialing-worker/
├── __init__.py              # Exports: DialerWorker, RetellClient, phone_utils, timezone_utils
├── retell_client.py         # HTTP wrapper for Retell AI API
├── phone_utils.py           # E.164 validation and formatting
├── timezone_utils.py        # Business hours checking, timezone helpers
├── worker.py                # RQ job handler and orchestrator
├── errors.py                # Custom exceptions
└── config.py                # Configuration (business hours defaults, etc.)
```

### Dependencies

**External:**
- `rq` (Redis Queue) — job scheduling
- `aiohttp` or `httpx` — async HTTP client for Retell API
- `pytz` — timezone handling
- `sqlalchemy` — async ORM (reuse from app/db/)
- `python-dotenv` — env variable loading

**Internal:**
- `app.db.session` — get async session
- `app.models` — Campaign, Contact, Call, DNCEntry models
- `app.db.queries` — parameterized DNC check query

---

## 3. Component Specifications

### 3.1 `retell_client.py` — Retell AI HTTP Wrapper

**Purpose:** Encapsulate all Retell API communication. No ORM, pure HTTP.

**Class: `RetellClient`**

```python
class RetellClient:
    def __init__(self, api_key: str, base_url: str = "https://api.retellai.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.http_client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"}
        )
    
    async def create_call(
        self,
        to_number: str,
        agent_id: str,
        campaign_id: str,
        dynamic_variables: dict | None = None,
    ) -> str:
        """
        Create an outbound call via Retell API.
        
        Args:
            to_number: E.164 format phone number (validated before calling)
            agent_id: Retell agent ID from campaign
            campaign_id: UUID of campaign (for tracking)
            dynamic_variables: Dict of variables to inject (first_name, company, etc.)
        
        Returns:
            call_id: Unique call ID from Retell
        
        Raises:
            RetellAPIError: If API call fails (retriable status codes: 429, 5xx)
            PhoneValidationError: If phone number is invalid (should not reach here)
        """
        payload = {
            "to_number": to_number,
            "agent_id": agent_id,
            "metadata": {
                "campaign_id": str(campaign_id),
                "source": "voice_agent_worker"
            }
        }
        if dynamic_variables:
            payload["dynamic_variables"] = dynamic_variables
        
        try:
            response = await self.http_client.post(
                f"{self.base_url}/v1/calls",
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data["call_id"]
        except httpx.HTTPStatusError as e:
            # Categorize error: transient (retry) vs permanent (fail)
            if e.response.status_code in (429, 500, 502, 503, 504):
                raise RetellAPIError(
                    message=f"Retell API error: {e.response.status_code}",
                    retriable=True,
                    status_code=e.response.status_code
                )
            else:
                raise RetellAPIError(
                    message=f"Retell API error: {e.response.status_code}",
                    retriable=False,
                    status_code=e.response.status_code
                )
        except httpx.TimeoutException:
            raise RetellAPIError(
                message="Retell API timeout",
                retriable=True,
                status_code=None
            )
    
    async def close(self):
        await self.http_client.aclose()
```

---

### 3.2 `phone_utils.py` — Phone Number Utilities

**Purpose:** Validate and normalize phone numbers to E.164 format.

```python
import re

def is_e164(phone_number: str) -> bool:
    """
    Check if phone number is valid E.164 format.
    
    Valid: +1234567890, +919876543210
    Invalid: 123-456-7890, (123) 456-7890, 9876543210 (no +)
    
    Args:
        phone_number: String to validate
    
    Returns:
        True if valid E.164, False otherwise
    """
    pattern = r"^\+[1-9]\d{1,14}$"
    return bool(re.match(pattern, phone_number))


def normalize_to_e164(phone_number: str, country_code: str = "US") -> str:
    """
    Normalize common phone formats to E.164.
    
    Handles:
    - 10-digit US: 1234567890 → +11234567890
    - Formatted: (123) 456-7890 → +11234567890
    - With country code: 91 9876543210 → +919876543210
    - Already E.164: +1234567890 → +1234567890
    
    Args:
        phone_number: Raw phone number string
        country_code: ISO country code (e.g., "US", "IN")
    
    Returns:
        E.164 formatted number
    
    Raises:
        PhoneValidationError: If number cannot be normalized
    """
    # Remove common formatting characters
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", phone_number.strip())
    
    # If already E.164, return as-is
    if is_e164(cleaned):
        return cleaned
    
    # Try adding country code prefix
    country_codes = {"US": "1", "IN": "91", "UK": "44"}
    cc = country_codes.get(country_code, "1")
    
    # If number starts with country code, add +
    if cleaned.startswith(cc):
        candidate = "+" + cleaned
    else:
        candidate = "+" + cc + cleaned
    
    if is_e164(candidate):
        return candidate
    
    raise PhoneValidationError(f"Cannot normalize {phone_number} to E.164")
```

---

### 3.3 `timezone_utils.py` — Timezone and Business Hours

**Purpose:** Check if current local time falls within business hours for a given timezone.

```python
from datetime import datetime
import pytz

def is_within_calling_hours(
    timezone: str,
    start_hour: int = 8,
    end_hour: int = 21
) -> bool:
    """
    Check if current time in given timezone falls within calling hours.
    
    Args:
        timezone: IANA timezone string (e.g., "Asia/Kolkata", "America/New_York")
        start_hour: Starting hour (24-hour, 0-23) - default 8am
        end_hour: Ending hour (24-hour, 0-23) - default 9pm (21:00)
    
    Returns:
        True if current local time is within [start_hour, end_hour), False otherwise
    
    Raises:
        ValueError: If timezone string is invalid
    """
    try:
        tz = pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Invalid timezone: {timezone}")
    
    now_local = datetime.now(tz)
    current_hour = now_local.hour
    
    # Simple hour check (ignores minutes, but sufficient for calling windows)
    return start_hour <= current_hour < end_hour


def get_local_time(timezone: str) -> datetime:
    """
    Get current time in a given timezone.
    
    Args:
        timezone: IANA timezone string
    
    Returns:
        Current datetime in the timezone (with tzinfo)
    """
    try:
        tz = pytz.timezone(timezone)
        return datetime.now(tz)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Invalid timezone: {timezone}")
```

---

### 3.4 `worker.py` — RQ Job Handler and Orchestrator

**Purpose:** Main worker loop - fetch leads, filter, validate, dispatch, rate-limit, handle errors.

```python
import asyncio
import logging
from datetime import datetime, timedelta

import sqlalchemy as sa
from app.db.session import get_session_factory
from app.models import Campaign, Contact, Call, CallStatus, ContactStatus
from app.dialing_worker.retell_client import RetellClient
from app.dialing_worker.phone_utils import is_e164
from app.dialing_worker.timezone_utils import is_within_calling_hours
from app.dialing_worker.errors import RetellAPIError, PhoneValidationError

logger = logging.getLogger(__name__)


class DialerWorker:
    def __init__(self, retell_api_key: str, poll_interval: int = 5):
        """
        Initialize dialer worker.
        
        Args:
            retell_api_key: Retell AI API key (from env)
            poll_interval: Seconds between poll cycles (default 5)
        """
        self.retell_client = RetellClient(api_key=retell_api_key)
        self.poll_interval = poll_interval
        self.session_factory = None
    
    async def initialize(self):
        """Initialize database session factory."""
        self.session_factory = await get_session_factory()
    
    async def run(self):
        """Main worker loop (runs forever until interrupted)."""
        logger.info("Dialing worker started")
        try:
            while True:
                await self.dial_batch()
                await asyncio.sleep(self.poll_interval)
        except KeyboardInterrupt:
            logger.info("Dialing worker stopped")
        finally:
            await self.retell_client.close()
    
    async def dial_batch(self):
        """
        Fetch pending leads, filter by timezone/DNC, dispatch calls at 1 CPS.
        """
        async with self.session_factory() as session:
            # 1. Fetch pending leads (DNC-filtered via SQL NOT EXISTS)
            stmt = sa.select(Contact).where(
                (Contact.status == ContactStatus.PENDING)
                & (Contact.next_retry_at <= sa.func.now())
                & ~sa.exists(
                    sa.select(1).select_from(DNCEntry)
                    .where(DNCEntry.phone_number == Contact.phone_number)
                )
            ).order_by(Contact.created_at).limit(50)
            
            result = await session.execute(stmt)
            leads = result.scalars().all()
            
            if not leads:
                logger.debug("No pending leads to dial")
                return
            
            logger.info(f"Fetched {len(leads)} pending leads")
            
            # 2. Filter by timezone (8am-9pm local time)
            dialable = [
                l for l in leads
                if is_within_calling_hours(l.timezone, start_hour=8, end_hour=21)
            ]
            
            logger.info(f"{len(dialable)} leads within calling hours")
            
            # 3. Dispatch calls with 1 CPS rate limit
            for lead in dialable:
                try:
                    await self._dispatch_call(session, lead)
                except Exception as e:
                    logger.error(f"Error dispatching call for lead {lead.id}: {e}")
                    continue
                
                # Strict 1 CPS rate limit
                await asyncio.sleep(1.0)
            
            # Commit all status updates
            await session.commit()
            logger.info(f"Dial batch complete ({len(dialable)} calls dispatched)")
    
    async def _dispatch_call(self, session, lead: Contact):
        """
        Dispatch a single call to Retell AI.
        
        Handles:
        - Phone validation
        - Retell API call
        - Status updates
        - Error categorization
        """
        # Validate phone number (E.164)
        if not is_e164(lead.phone_number):
            logger.warning(f"Invalid phone {lead.phone_number} for lead {lead.id}")
            lead.status = ContactStatus.FAILED
            return
        
        # Get campaign (for agent_id, business hours config)
        campaign = await session.get(Campaign, lead.campaign_id)
        if not campaign:
            logger.error(f"Campaign {lead.campaign_id} not found for lead {lead.id}")
            lead.status = ContactStatus.FAILED
            return
        
        # Build dynamic variables
        dynamic_vars = {
            "first_name": lead.first_name or "",
            "company": lead.company or "",
        }
        if lead.custom_vars:
            dynamic_vars.update(lead.custom_vars)
        
        # Dispatch to Retell AI
        try:
            call_id = await self.retell_client.create_call(
                to_number=lead.phone_number,
                agent_id=campaign.retell_agent_id,  # Assume campaign has this
                campaign_id=lead.campaign_id,
                dynamic_variables=dynamic_vars
            )
            
            # Create call_logs entry
            call_log = Call(
                lead_id=lead.id,
                retell_call_id=call_id,
                status=CallStatus.CALLING
            )
            session.add(call_log)
            
            # Update lead status
            lead.status = ContactStatus.CALLING
            logger.info(f"Call dispatched for lead {lead.id} (call_id={call_id})")
        
        except RetellAPIError as e:
            await self._handle_retell_error(lead, e)
        except Exception as e:
            logger.exception(f"Unexpected error for lead {lead.id}: {e}")
            lead.status = ContactStatus.FAILED
    
    async def _handle_retell_error(self, lead: Contact, error: RetellAPIError):
        """
        Handle Retell API errors - categorize as retriable vs permanent.
        """
        if error.retriable:
            # Retry: increment counter, set backoff
            lead.retry_count = (lead.retry_count or 0) + 1
            backoff_seconds = min(60, 2 ** lead.retry_count)  # Exponential backoff
            lead.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
            lead.status = ContactStatus.PENDING
            logger.warning(
                f"Retriable error for lead {lead.id}, retry #{lead.retry_count} "
                f"in {backoff_seconds}s: {error.message}"
            )
        else:
            # Permanent failure
            lead.status = ContactStatus.FAILED
            logger.error(f"Permanent error for lead {lead.id}: {error.message}")


async def dial_worker_job():
    """
    RQ job entrypoint.
    
    Called by: rq worker (reads from Redis queue)
    """
    api_key = os.getenv("RETELL_API_KEY")
    if not api_key:
        raise ValueError("RETELL_API_KEY not set in environment")
    
    worker = DialerWorker(retell_api_key=api_key)
    await worker.initialize()
    await worker.run()
```

---

### 3.5 `errors.py` — Custom Exceptions

```python
class PhoneValidationError(Exception):
    """Raised when phone number validation fails."""
    pass


class RetellAPIError(Exception):
    """Raised when Retell API call fails."""
    
    def __init__(self, message: str, retriable: bool, status_code: int | None = None):
        self.message = message
        self.retriable = retriable
        self.status_code = status_code
        super().__init__(message)
```

---

### 3.6 `config.py` — Configuration

```python
from dataclasses import dataclass

@dataclass
class DialerConfig:
    """Configuration for dialing worker."""
    
    # Business hours (24-hour format)
    DEFAULT_START_HOUR: int = 8      # 8am
    DEFAULT_END_HOUR: int = 21       # 9pm
    
    # Rate limiting
    CALLS_PER_SECOND: float = 1.0    # Strict 1 CPS
    
    # Poll interval
    POLL_INTERVAL_SECONDS: int = 5   # Check for new leads every 5 seconds
    
    # Batch size
    BATCH_SIZE: int = 50             # Max leads per batch
    
    # Retry strategy
    MAX_RETRIES: int = 5             # Maximum retry attempts per lead
    INITIAL_BACKOFF_SECONDS: int = 2 # Starting backoff (exponential: 2, 4, 8, 16, 32)
```

---

## 4. Data Flow

### 4.1 Lead Polling & Filtering

```
1. Query database (SQL NOT EXISTS for DNC)
   ↓
2. Filter by timezone (is_within_calling_hours)
   ↓
3. Validate phone numbers (E.164 check)
   ↓
4. Ready to dispatch
```

### 4.2 Call Dispatch

```
For each lead:
1. Build dynamic variables (first_name, company, custom_vars)
2. Call Retell API (create_call)
3. On success:
   - Create call_logs entry (status=calling)
   - Update lead status (pending → calling)
   - Sleep 1.0 seconds
4. On error:
   - If retriable: set next_retry_at, keep status pending
   - If permanent: mark status failed
```

---

## 5. Error Handling Matrix

| Error | Category | Action | Lead Status |
|---|---|---|---|
| Invalid E.164 | Validation | Log warning, skip | `failed` |
| Phone in DNC | Validation | Log, mark for compliance | `failed_dnc` |
| Invalid timezone | Validation | Skip, investigate manually | `pending` (no change) |
| Retell API timeout | Transient | Increment retry, set backoff | `pending` |
| Retell API 5xx | Transient | Increment retry, set backoff | `pending` |
| Retell API 4xx (non-validation) | Permanent | Log error | `failed` |
| DB connection error | Fatal | Exit worker, let RQ retry entire job | (no change) |

---

## 6. Testing Strategy

### 6.1 Unit Tests

- `test_phone_utils.py`: E.164 validation, normalization (edge cases, DST)
- `test_timezone_utils.py`: Business hours checks, invalid timezones
- `test_errors.py`: Custom exception behavior

### 6.2 Integration Tests

- Mock Retell API, verify lead status transitions
- Test rate limiting (1 CPS enforcement)
- Test error handling (retriable vs permanent)
- Test batch fetch with DNC filtering

### 6.3 E2E Tests

- Real Redis queue (optional)
- Small test dataset (5-10 leads)
- Verify full cycle: fetch → dial → update

---

## 7. Configuration & Environment

**Required Environment Variables:**

```env
RETELL_API_KEY=your_api_key_here
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/voice_agent
REDIS_URL=redis://localhost:6379/0
```

**Campaign Configuration (in campaigns table):**

```python
campaigns.llm_config = {
    "retell_agent_id": "agent_abc123",
    "start_hour": 8,        # Optional: override default 8am
    "end_hour": 21,         # Optional: override default 9pm
}
```

---

## 8. Deployment

### Starting the Worker

```bash
# Install RQ
pip install rq

# Start worker (connects to Redis, polls for dial_worker_job)
rq worker

# Or with specific queue name
rq worker dialing_queue
```

### Monitoring

- Redis queue depth: `rq info` command
- Log files: Check application logs for dispatch status
- Metrics: Count of leads dialed, errors, retries (via logging)

---

## 9. Success Criteria

- ✅ Worker fetches and dials leads at exactly 1 CPS (no faster, no slower)
- ✅ DNC check via SQL NOT EXISTS (verified in database query)
- ✅ Timezone gate respects lead.timezone (never assumes IST)
- ✅ Errors categorized: retriable (exponential backoff) vs permanent (failed)
- ✅ Phone numbers validated to E.164 before dispatch
- ✅ All database queries use parameterized SQLAlchemy (no string interpolation)
- ✅ Business hours configurable per campaign
- ✅ Unit + integration tests passing (>90% code coverage)
- ✅ Worker runs as standalone RQ job (separate process)

---

## 10. Future Enhancements (Out of Scope)

- Pause/resume campaign dialing (admin endpoint)
- Dynamic rate limiting based on Retell API load
- Metrics collection (Prometheus/CloudWatch)
- Dead letter queue for unrecoverable leads
- Scheduled batch processing (cron-based instead of continuous poll)

---

*Design document prepared by Claude Code brainstorming skill.*
