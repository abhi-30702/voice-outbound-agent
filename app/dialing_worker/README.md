# Dialing Worker Module

Autonomous outbound dialing worker for voice-outbound-agent. Implements RQ-based job queue processing with 1 CPS rate limiting, timezone-aware calling hours, DNC filtering, and exponential backoff retry logic.

## Overview

The dialing worker is responsible for:
1. Fetching pending leads from PostgreSQL with DNC filtering (SQL NOT EXISTS)
2. Filtering by timezone (8am-9pm local time)
3. Dispatching outbound calls via Retell AI API
4. Handling errors with exponential backoff (max 60 seconds)
5. Enforcing 1 call-per-second (CPS) rate limit via `asyncio.sleep(1.0)`

## Architecture

```
┌──────────────────────────────────────────────┐
│  PostgreSQL Database                         │
│  • leads (PENDING status)                    │
│  • dnc_registry (phone numbers to skip)      │
│  • campaigns (agent configs)                 │
└────────────┬─────────────────────────────────┘
             │ (DNC-filtered query via NOT EXISTS)
             ▼
┌──────────────────────────────────────────────┐
│  DialerWorker                                │
│  • Fetch batch (50 leads max)                │
│  • Filter by timezone                        │
│  • Dispatch calls (1 CPS limit)              │
└────────────┬─────────────────────────────────┘
             │ (asyncio.sleep(1.0) after each)
             ▼
┌──────────────────────────────────────────────┐
│  Retell AI API                               │
│  POST /v1/call                               │
│  Returns: call_id, status                    │
└──────────────────────────────────────────────┘
```

## Module Components

### Core Classes

#### `DialerWorker`
Main worker class that orchestrates the dialing loop.

**Methods:**
- `__init__(config: DialerConfig)` - Initialize with configuration
- `async initialize()` - Set up database session factory
- `async run()` - Main event loop (blocking)
- `async dial_batch()` - Fetch and dial leads
- `async _fetch_pending_leads(session)` - SQL query for leads
- `async _dispatch_call(session, lead)` - Dispatch a single call
- `async _handle_retell_error(session, lead, error)` - Error handling with backoff
- `stop()` - Stop the worker gracefully

#### `RetellClient`
Async HTTP wrapper for Retell AI API.

**Methods:**
- `__init__(api_key, base_url, timeout)` - Initialize client
- `async create_call(to_number, agent_id, dynamic_variables)` - Create call via API
- `async close()` - Clean up HTTP connection

#### Custom Exceptions
- `DialingWorkerError` - Base exception
- `PhoneValidationError` - Invalid E.164 format
- `RetellAPIError` - API request failure (includes `retriable` flag and `status_code`)

### Utility Modules

#### `phone_utils.py`
Phone number validation and normalization.

**Functions:**
- `is_e164(phone_number: str) -> bool` - Validate E.164 format
- `normalize_to_e164(phone_number: str, country_code: str) -> str` - Normalize to E.164

#### `timezone_utils.py`
Timezone-aware business hours checking.

**Functions:**
- `get_local_time(timezone: str) -> datetime` - Get current time in timezone
- `is_within_calling_hours(timezone, start_hour=8, end_hour=21) -> bool` - Check if within calling hours

#### `config.py`
Configuration dataclass with sensible defaults.

**Fields:**
- `retell_api_key` (required) - Retell API key
- `retell_base_url` - Default: https://api.retellai.com
- `retell_timeout_sec` - Default: 30.0
- `batch_size` - Default: 50 leads per batch
- `poll_interval_sec` - Default: 5 seconds
- `start_hour` - Default: 8 (8am)
- `end_hour` - Default: 21 (9pm)
- `max_retries` - Default: 5

## Key Features

### 1. SQL-Level DNC Filtering
Complies with CLAUDE.md requirement: "DNC check MUST be in SQL (NOT EXISTS), never application-level filtering."

```sql
SELECT l.* FROM agent_operations.leads l
WHERE l.status = 'pending'
  AND NOT EXISTS (
      SELECT 1 FROM agent_operations.dnc_registry d
      WHERE d.phone_number = l.phone_number
  )
```

### 2. 1 CPS Rate Limiting
Enforces exactly 1 call per second via `asyncio.sleep(1.0)` after each dispatch.

```python
for lead in dialable_leads:
    await self._dispatch_call(session, lead)
    await asyncio.sleep(1.0)  # Hard 1 CPS limit
```

### 3. Timezone-Aware Calling Hours
Uses `pytz` to respect lead's local timezone (8am-9pm default).

```python
dialable = [
    l for l in leads
    if is_within_calling_hours(l.timezone, start_hour=8, end_hour=21)
]
```

### 4. Exponential Backoff
Retriable errors (429, 5xx, timeout) trigger exponential backoff with 60-second cap.

```
Retry 1: 2^1 = 2 seconds
Retry 2: 2^2 = 4 seconds
Retry 3: 2^3 = 8 seconds
Retry 4: 2^4 = 16 seconds
Retry 5: 2^5 = 32 seconds
Retry 6+: min(2^n, 60) = 60 seconds
```

### 5. E.164 Phone Validation
All numbers validated before dispatch.

```
Valid:   +11234567890, +919876543210
Invalid: 123-456-7890, (123) 456-7890, 9876543210
```

### 6. Parameterized SQL Queries
All database queries use bound parameters to prevent SQL injection.

```python
query = text("""
    SELECT * FROM agent_operations.leads
    WHERE phone_number = :phone_number
""")
result = await session.execute(query, {"phone_number": phone})
```

## Error Handling

### Retriable Errors
Auto-retry with exponential backoff, keep lead status as PENDING:
- 429 Too Many Requests (rate limit)
- 5xx server errors (500, 502, 503, 504)
- Timeouts
- Network errors (DNS failure, connection refused)

### Permanent Errors
Mark lead as FAILED, do not retry:
- 400 Bad Request (invalid E.164)
- 401 Unauthorized (auth failure)
- 403 Forbidden

## Usage

### Basic Usage

```python
from app.dialing_worker.config import DialerConfig
from app.dialing_worker.worker import DialerWorker

config = DialerConfig(
    retell_api_key="your-api-key",
    batch_size=50,
    poll_interval_sec=5,
)

worker = DialerWorker(config)

# Run the worker (blocking)
import asyncio
asyncio.run(worker.run())
```

### With RQ Job Queue

```python
from rq import Queue
from redis import Redis
from app.dialing_worker.worker import DialerWorker
from app.dialing_worker.config import DialerConfig

redis_conn = Redis()
q = Queue(connection=redis_conn)

def dial_job():
    config = DialerConfig(retell_api_key=os.getenv("RETELL_API_KEY"))
    worker = DialerWorker(config)
    asyncio.run(worker.run())

job = q.enqueue(dial_job)
```

## Testing

### Unit Tests
```bash
pytest tests/unit/test_phone_utils.py -v
pytest tests/unit/test_timezone_utils.py -v
pytest tests/unit/test_retell_client.py -v
```

### Integration Tests
```bash
pytest tests/integration/test_dialing_worker.py -v
pytest tests/integration/test_rate_limiting.py -v
pytest tests/integration/test_dnc_filtering.py -v
```

### Coverage
```bash
pytest tests/unit/ tests/integration/test_dialing_worker.py \
  --cov=app/dialing_worker --cov-report=term-missing
```

Target: >85% coverage

## Constraints (from CLAUDE.md)

1. **DNC Check:** Must be in SQL (NOT EXISTS), never application-level filtering ✓
2. **Rate Limit:** Must enforce 1 CPS hard limit via asyncio.sleep(1.0) ✓
3. **Timezone Gate:** Must use lead.timezone; never assume IST ✓
4. **Parameterized Queries:** All SQL must use bound parameters, no string interpolation ✓
5. **Phone Validation:** E.164 format required ✓
6. **Error Handling:** Retriable vs permanent error classification ✓

## Monitoring & Observability

### Logging
All components log at INFO/WARNING/ERROR levels:
- INFO: Successful calls, retries scheduled
- WARNING: Permanent errors
- ERROR: Validation failures, missing campaigns

### Metrics
Captured in call_logs table:
- call_id
- start_time / end_time / duration_sec
- disconnect_reason
- recording_url

### KPIs (from PRD.md)
- End-to-end response latency: < 500ms
- First-5-second detection rate: < 20%
- Call abandon rate: < 15%
- DNC scrub miss rate: 0%

## Future Enhancements

1. **CNAM Rotation:** Rotate caller ID by campaign
2. **Webhook Integration:** Receive call_started, call_ended, call_analyzed events
3. **Custom Variables:** Inject lead data into agent prompts
4. **Circuit Breaker:** Skip dials if Retell API is unhealthy
5. **Metrics Export:** Prometheus /metrics endpoint

## See Also

- `/app/db-schema/` - Database schema and migrations
- `/app/models/` - ORM models (Lead, Campaign, Call, etc.)
- `/app/retell-integration/` - Retell AI integration (TBD)
- `/PRD.md` - Product requirements
- `/CLAUDE.md` - Architecture constraints
