# Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Next.js 14 dashboard (live call monitor, campaign manager, KPI charts) backed by a new `app/dashboard_api/` FastAPI module with REST + WebSocket endpoints.

**Architecture:** New `app/dashboard_api/` APIRouter mounted on the existing FastAPI app at port 8000. Next.js 14 App Router at port 3000 proxies `/api/*` to FastAPI and opens a native WebSocket to `/ws/calls`. Webhook receiver handlers call `broadcast()` after writing to the DB so live call events propagate to the browser in real time.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async (asyncpg), Pydantic v2, pytest + pytest-asyncio, Next.js 14, React 18, Tailwind CSS 3, Recharts, SWR

---

## File Map

**Created — backend:**
- `app/dashboard_api/__init__.py`
- `app/dashboard_api/schemas.py` — Pydantic request/response models
- `app/dashboard_api/websocket.py` — `ConnectionManager` + module-level `broadcast()` coroutine
- `app/dashboard_api/kpi.py` — `get_kpi(db, range_)` query function
- `app/dashboard_api/campaigns.py` — `list_campaigns`, `create_campaign`, `patch_campaign_status`
- `app/dashboard_api/leads.py` — `list_leads`, `parse_csv`, `upload_leads`, `assign_leads`
- `app/dashboard_api/router.py` — two APIRouters (`api_router` prefix `/api`, `ws_router` for `/ws/calls`)

**Modified — backend:**
- `app/webhook_receiver/main.py` — mount `api_router` and `ws_router`
- `app/webhook_receiver/handlers/transcript_updated.py` — call `broadcast()`
- `app/webhook_receiver/handlers/call_started.py` — call `broadcast()` after DB write
- `app/webhook_receiver/handlers/call_ended.py` — call `broadcast()` after DB write

**Created — tests:**
- `tests/unit/test_dashboard_schemas.py`
- `tests/unit/test_dashboard_websocket.py`
- `tests/unit/test_dashboard_kpi.py`
- `tests/unit/test_dashboard_campaigns.py`
- `tests/unit/test_dashboard_leads.py`

**Created — frontend:**
- `app/dashboard/package.json`
- `app/dashboard/tsconfig.json`
- `app/dashboard/next.config.js`
- `app/dashboard/tailwind.config.js`
- `app/dashboard/postcss.config.js`
- `app/dashboard/app/globals.css`
- `app/dashboard/app/layout.tsx`
- `app/dashboard/app/page.tsx`
- `app/dashboard/app/campaigns/page.tsx`
- `app/dashboard/app/kpi/page.tsx`
- `app/dashboard/components/LiveCallFeed.tsx`
- `app/dashboard/components/CallCard.tsx`
- `app/dashboard/components/CampaignTable.tsx`
- `app/dashboard/components/CreateCampaignModal.tsx`
- `app/dashboard/components/LeadUpload.tsx`
- `app/dashboard/components/KpiChart.tsx`
- `app/dashboard/components/RangeSelector.tsx`

**Created — infra:**
- `docker-compose.yml`

---

## Task 1: Pydantic Schemas

**Files:**
- Create: `app/dashboard_api/__init__.py`
- Create: `app/dashboard_api/schemas.py`
- Create: `tests/unit/test_dashboard_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_dashboard_schemas.py
import pytest
import uuid
from pydantic import ValidationError
from app.dashboard_api.schemas import (
    CampaignOut, CampaignCreate, CampaignStatusPatch,
    LeadOut, LeadUploadResult, LeadAssign, KpiOut,
)


def test_campaign_out_serializes():
    cid = uuid.uuid4()
    c = CampaignOut(id=cid, name="Test", status="draft", lead_count=5)
    d = c.model_dump()
    assert d["id"] == cid
    assert d["lead_count"] == 5


def test_campaign_create_requires_name():
    with pytest.raises(ValidationError):
        CampaignCreate(prompt_template={})


def test_kpi_out_serializes():
    k = KpiOut(total_leads=100, calls_made=50, connection_rate=0.7, avg_duration_sec=42.5)
    d = k.model_dump()
    assert d["connection_rate"] == 0.7


def test_lead_upload_result_serializes():
    r = LeadUploadResult(inserted=10, skipped=2)
    assert r.inserted == 10
    assert r.skipped == 2


def test_lead_assign_requires_lead_ids():
    with pytest.raises(ValidationError):
        LeadAssign(campaign_id=uuid.uuid4())


def test_campaign_status_patch_requires_status():
    with pytest.raises(ValidationError):
        CampaignStatusPatch()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_dashboard_schemas.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.dashboard_api'`

- [ ] **Step 3: Create package init and schemas**

```python
# app/dashboard_api/__init__.py
```
(empty file)

```python
# app/dashboard_api/schemas.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CampaignOut(BaseModel):
    id: UUID
    name: str
    status: str
    lead_count: int


class CampaignCreate(BaseModel):
    name: str
    prompt_template: dict
    llm_config: dict = {}


class CampaignStatusPatch(BaseModel):
    status: str  # "active" | "paused" | "completed"


class LeadOut(BaseModel):
    id: UUID
    phone_number: str
    first_name: str | None
    last_name: str | None
    status: str
    campaign_id: UUID | None


class LeadUploadResult(BaseModel):
    inserted: int
    skipped: int


class LeadAssign(BaseModel):
    lead_ids: list[UUID]
    campaign_id: UUID


class ActiveCall(BaseModel):
    call_id: str
    lead_id: UUID | None
    status: str
    start_time: datetime | None


class KpiOut(BaseModel):
    total_leads: int
    calls_made: int
    connection_rate: float
    avg_duration_sec: float
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/unit/test_dashboard_schemas.py -v
```
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/dashboard_api/__init__.py app/dashboard_api/schemas.py tests/unit/test_dashboard_schemas.py
git commit -m "feat: add dashboard_api package and Pydantic schemas"
```

---

## Task 2: WebSocket ConnectionManager

**Files:**
- Create: `app/dashboard_api/websocket.py`
- Create: `tests/unit/test_dashboard_websocket.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_dashboard_websocket.py
import pytest
from unittest.mock import AsyncMock
from app.dashboard_api.websocket import ConnectionManager


@pytest.mark.asyncio
async def test_connect_adds_to_set():
    manager = ConnectionManager()
    ws = AsyncMock()
    await manager.connect(ws)
    assert ws in manager._connections


@pytest.mark.asyncio
async def test_disconnect_removes_from_set():
    manager = ConnectionManager()
    ws = AsyncMock()
    await manager.connect(ws)
    manager.disconnect(ws)
    assert ws not in manager._connections


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_connected():
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await manager.connect(ws1)
    await manager.connect(ws2)
    await manager.broadcast({"event": "test"})
    ws1.send_json.assert_called_once_with({"event": "test"})
    ws2.send_json.assert_called_once_with({"event": "test"})


@pytest.mark.asyncio
async def test_broadcast_skips_and_removes_disconnected_client():
    manager = ConnectionManager()
    ws = AsyncMock()
    ws.send_json.side_effect = Exception("disconnected")
    await manager.connect(ws)
    await manager.broadcast({"event": "test"})  # must not raise
    assert ws not in manager._connections


@pytest.mark.asyncio
async def test_broadcast_with_no_connections_is_noop():
    manager = ConnectionManager()
    await manager.broadcast({"event": "test"})  # must not raise


@pytest.mark.asyncio
async def test_disconnect_nonexistent_is_noop():
    manager = ConnectionManager()
    ws = AsyncMock()
    manager.disconnect(ws)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_dashboard_websocket.py -v
```
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement ConnectionManager**

```python
# app/dashboard_api/websocket.py
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, message: dict) -> None:
        dead: set[WebSocket] = set()
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        self._connections -= dead


manager = ConnectionManager()


async def broadcast(message: dict) -> None:
    """Module-level coroutine imported by webhook handlers."""
    await manager.broadcast(message)
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/unit/test_dashboard_websocket.py -v
```
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/dashboard_api/websocket.py tests/unit/test_dashboard_websocket.py
git commit -m "feat: add ConnectionManager and broadcast coroutine"
```

---

## Task 3: KPI Query Function

**Files:**
- Create: `app/dashboard_api/kpi.py`
- Create: `tests/unit/test_dashboard_kpi.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_dashboard_kpi.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.dashboard_api.kpi import get_kpi
from app.dashboard_api.schemas import KpiOut


def _db_with_scalars(*values):
    """Build an AsyncMock db whose execute() returns scalar_one() for each value in order."""
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one=MagicMock(return_value=v)) for v in values
    ]
    return db


@pytest.mark.asyncio
async def test_get_kpi_today_returns_kpi_out():
    db = _db_with_scalars(200, 50, 35, 45.0)
    result = await get_kpi(db, "today")
    assert isinstance(result, KpiOut)
    assert result.total_leads == 200
    assert result.calls_made == 50
    assert result.connection_rate == round(35 / 50, 4)


@pytest.mark.asyncio
async def test_get_kpi_zero_calls_gives_zero_rate_and_duration():
    db = _db_with_scalars(100, 0, 0, None)
    result = await get_kpi(db, "today")
    assert result.connection_rate == 0.0
    assert result.avg_duration_sec == 0.0


@pytest.mark.asyncio
async def test_get_kpi_7d_runs_four_queries():
    db = _db_with_scalars(0, 0, 0, None)
    await get_kpi(db, "7d")
    assert db.execute.call_count == 4


@pytest.mark.asyncio
async def test_get_kpi_30d_runs_four_queries():
    db = _db_with_scalars(0, 0, 0, None)
    await get_kpi(db, "30d")
    assert db.execute.call_count == 4


@pytest.mark.asyncio
async def test_get_kpi_connection_rate_rounds_to_four_decimals():
    db = _db_with_scalars(100, 3, 1, 60.0)
    result = await get_kpi(db, "today")
    assert result.connection_rate == round(1 / 3, 4)
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_dashboard_kpi.py -v
```
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `get_kpi`**

```python
# app/dashboard_api/kpi.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dashboard_api.schemas import KpiOut
from app.models.call import Call, CallStatus
from app.models.contact import Contact


async def get_kpi(db: AsyncSession, range_: str) -> KpiOut:
    now = datetime.now(tz=timezone.utc)
    if range_ == "7d":
        cutoff = now - timedelta(days=7)
    elif range_ == "30d":
        cutoff = now - timedelta(days=30)
    else:  # "today"
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_leads = (
        await db.execute(select(func.count()).select_from(Contact))
    ).scalar_one()

    calls_made = (
        await db.execute(
            select(func.count()).select_from(Call).where(Call.created_at >= cutoff)
        )
    ).scalar_one()

    completed = (
        await db.execute(
            select(func.count())
            .select_from(Call)
            .where(Call.created_at >= cutoff, Call.status == CallStatus.COMPLETED)
        )
    ).scalar_one()

    avg_dur_raw = (
        await db.execute(
            select(func.avg(Call.duration_sec)).where(
                Call.created_at >= cutoff, Call.status == CallStatus.COMPLETED
            )
        )
    ).scalar_one()

    connection_rate = round(completed / calls_made, 4) if calls_made > 0 else 0.0
    avg_duration_sec = round(float(avg_dur_raw), 2) if avg_dur_raw is not None else 0.0

    return KpiOut(
        total_leads=total_leads,
        calls_made=calls_made,
        connection_rate=connection_rate,
        avg_duration_sec=avg_duration_sec,
    )
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/unit/test_dashboard_kpi.py -v
```
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/dashboard_api/kpi.py tests/unit/test_dashboard_kpi.py
git commit -m "feat: add KPI query function"
```

---

## Task 4: Campaign Service Functions

**Files:**
- Create: `app/dashboard_api/campaigns.py`
- Create: `tests/unit/test_dashboard_campaigns.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_dashboard_campaigns.py
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from app.dashboard_api.campaigns import list_campaigns, create_campaign, patch_campaign_status
from app.dashboard_api.schemas import CampaignCreate, CampaignStatusPatch


@pytest.mark.asyncio
async def test_list_campaigns_returns_list():
    db = AsyncMock()
    row = MagicMock(id=uuid.uuid4(), name="Camp A", status="draft", lead_count=3)
    db.execute.return_value = MagicMock(all=MagicMock(return_value=[row]))
    result = await list_campaigns(db)
    assert len(result) == 1
    assert result[0].name == "Camp A"
    assert result[0].lead_count == 3


@pytest.mark.asyncio
async def test_list_campaigns_empty():
    db = AsyncMock()
    db.execute.return_value = MagicMock(all=MagicMock(return_value=[]))
    result = await list_campaigns(db)
    assert result == []


@pytest.mark.asyncio
async def test_create_campaign_returns_draft():
    db = AsyncMock()
    db.flush = AsyncMock()
    body = CampaignCreate(name="New Camp", prompt_template={"template_key": "real_estate"})
    result = await create_campaign(db, body)
    assert result.name == "New Camp"
    assert result.status == "draft"
    assert result.lead_count == 0
    db.add.assert_called_once()
    db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_patch_campaign_status_updates_and_returns():
    db = AsyncMock()
    campaign = MagicMock()
    campaign.id = uuid.uuid4()
    campaign.name = "Camp"
    db.get.return_value = campaign
    db.flush = AsyncMock()
    body = CampaignStatusPatch(status="paused")
    result = await patch_campaign_status(db, campaign.id, body)
    assert campaign.status == "paused"
    assert result.name == "Camp"


@pytest.mark.asyncio
async def test_patch_campaign_status_raises_if_not_found():
    db = AsyncMock()
    db.get.return_value = None
    db.flush = AsyncMock()
    body = CampaignStatusPatch(status="active")
    with pytest.raises(ValueError, match="not found"):
        await patch_campaign_status(db, uuid.uuid4(), body)
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_dashboard_campaigns.py -v
```
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement campaign service**

```python
# app/dashboard_api/campaigns.py
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dashboard_api.schemas import CampaignCreate, CampaignOut, CampaignStatusPatch
from app.models.campaign import Campaign, CampaignStatus
from app.models.contact import Contact


async def list_campaigns(db: AsyncSession) -> list[CampaignOut]:
    result = await db.execute(
        select(
            Campaign.id,
            Campaign.name,
            Campaign.status,
            func.count(Contact.id).label("lead_count"),
        )
        .outerjoin(Contact, Contact.campaign_id == Campaign.id)
        .group_by(Campaign.id)
    )
    return [
        CampaignOut(id=r.id, name=r.name, status=r.status, lead_count=r.lead_count)
        for r in result.all()
    ]


async def create_campaign(db: AsyncSession, body: CampaignCreate) -> CampaignOut:
    campaign = Campaign(
        id=uuid.uuid4(),
        name=body.name,
        status=CampaignStatus.DRAFT,
        prompt_template=body.prompt_template,
        llm_config=body.llm_config,
    )
    db.add(campaign)
    await db.flush()
    return CampaignOut(id=campaign.id, name=campaign.name, status=campaign.status, lead_count=0)


async def patch_campaign_status(
    db: AsyncSession, campaign_id: uuid.UUID, body: CampaignStatusPatch
) -> CampaignOut:
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None:
        raise ValueError(f"Campaign {campaign_id} not found")
    campaign.status = CampaignStatus(body.status)
    await db.flush()
    return CampaignOut(id=campaign.id, name=campaign.name, status=campaign.status, lead_count=0)
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/unit/test_dashboard_campaigns.py -v
```
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/dashboard_api/campaigns.py tests/unit/test_dashboard_campaigns.py
git commit -m "feat: add campaign service functions"
```

---

## Task 5: Lead Service Functions

**Files:**
- Create: `app/dashboard_api/leads.py`
- Create: `tests/unit/test_dashboard_leads.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_dashboard_leads.py
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from app.dashboard_api.leads import parse_csv, upload_leads, list_leads, assign_leads
from app.dashboard_api.schemas import LeadAssign


def test_parse_csv_valid_rows():
    content = b"phone_number,timezone,first_name\n+91999,Asia/Kolkata,Ravi\n+91888,Asia/Kolkata,Priya\n"
    rows, skipped = parse_csv(content)
    assert len(rows) == 2
    assert skipped == 0
    assert rows[0]["phone_number"] == "+91999"


def test_parse_csv_skips_row_with_empty_phone():
    content = b"phone_number,timezone\n,Asia/Kolkata\n+91999,Asia/Kolkata\n"
    rows, skipped = parse_csv(content)
    assert len(rows) == 1
    assert skipped == 1


def test_parse_csv_skips_row_with_empty_timezone():
    content = b"phone_number,timezone\n+91999,\n+91888,Asia/Kolkata\n"
    rows, skipped = parse_csv(content)
    assert len(rows) == 1
    assert skipped == 1


def test_parse_csv_empty_file_returns_empty():
    rows, skipped = parse_csv(b"")
    assert rows == []
    assert skipped == 0


def test_parse_csv_missing_required_column_raises():
    content = b"phone_number,first_name\n+91999,Ravi\n"
    with pytest.raises(ValueError, match="missing required columns"):
        parse_csv(content)


@pytest.mark.asyncio
async def test_upload_leads_inserts_all_valid_rows():
    db = AsyncMock()
    db.flush = AsyncMock()
    content = b"phone_number,timezone\n+91999,Asia/Kolkata\n+91888,Asia/Kolkata\n"
    result = await upload_leads(db, content)
    assert result.inserted == 2
    assert result.skipped == 0
    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_upload_leads_reports_skipped_count():
    db = AsyncMock()
    db.flush = AsyncMock()
    content = b"phone_number,timezone\n,Asia/Kolkata\n+91888,Asia/Kolkata\n"
    result = await upload_leads(db, content)
    assert result.inserted == 1
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_assign_leads_sets_campaign_id():
    db = AsyncMock()
    db.flush = AsyncMock()
    cid = uuid.uuid4()
    lead1 = MagicMock(campaign_id=None)
    lead2 = MagicMock(campaign_id=None)
    db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[lead1, lead2])))
    )
    body = LeadAssign(lead_ids=[uuid.uuid4(), uuid.uuid4()], campaign_id=cid)
    count = await assign_leads(db, body)
    assert count == 2
    assert lead1.campaign_id == cid
    assert lead2.campaign_id == cid


@pytest.mark.asyncio
async def test_list_leads_returns_all_when_no_filter():
    db = AsyncMock()
    c = MagicMock(
        id=uuid.uuid4(), phone_number="+91999", first_name="Ravi",
        last_name=None, status="pending", campaign_id=None
    )
    db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[c])))
    )
    result = await list_leads(db)
    assert len(result) == 1
    assert result[0].phone_number == "+91999"
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_dashboard_leads.py -v
```
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement lead service**

```python
# app/dashboard_api/leads.py
from __future__ import annotations

import csv
import io
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dashboard_api.schemas import LeadAssign, LeadOut, LeadUploadResult
from app.models.contact import Contact, ContactStatus

_REQUIRED_COLUMNS = {"phone_number", "timezone"}


def parse_csv(content: bytes) -> tuple[list[dict], int]:
    """Return (valid_rows, skipped_count). Raises ValueError for missing required columns."""
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], 0
    cols = {f.strip() for f in reader.fieldnames}
    missing = _REQUIRED_COLUMNS - cols
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    rows: list[dict] = []
    skipped = 0
    for row in reader:
        phone = row.get("phone_number", "").strip()
        tz = row.get("timezone", "").strip()
        if not phone or not tz:
            skipped += 1
            continue
        rows.append(row)
    return rows, skipped


async def list_leads(
    db: AsyncSession,
    campaign_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[LeadOut]:
    stmt = select(Contact)
    if campaign_id is not None:
        stmt = stmt.where(Contact.campaign_id == campaign_id)
    if status is not None:
        stmt = stmt.where(Contact.status == ContactStatus(status))
    result = await db.execute(stmt)
    contacts = result.scalars().all()
    return [
        LeadOut(
            id=c.id,
            phone_number=c.phone_number,
            first_name=c.first_name,
            last_name=c.last_name,
            status=c.status,
            campaign_id=c.campaign_id,
        )
        for c in contacts
    ]


async def upload_leads(
    db: AsyncSession,
    content: bytes,
    campaign_id: uuid.UUID | None = None,
) -> LeadUploadResult:
    rows, skipped = parse_csv(content)
    for row in rows:
        contact = Contact(
            id=uuid.uuid4(),
            phone_number=row["phone_number"].strip(),
            timezone=row["timezone"].strip(),
            first_name=row.get("first_name", "").strip() or None,
            last_name=row.get("last_name", "").strip() or None,
            company=row.get("company", "").strip() or None,
            campaign_id=campaign_id,
            status=ContactStatus.PENDING,
        )
        db.add(contact)
    await db.flush()
    return LeadUploadResult(inserted=len(rows), skipped=skipped)


async def assign_leads(db: AsyncSession, body: LeadAssign) -> int:
    result = await db.execute(select(Contact).where(Contact.id.in_(body.lead_ids)))
    contacts = result.scalars().all()
    for c in contacts:
        c.campaign_id = body.campaign_id
    await db.flush()
    return len(contacts)
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/unit/test_dashboard_leads.py -v
```
Expected: 9 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/dashboard_api/leads.py tests/unit/test_dashboard_leads.py
git commit -m "feat: add lead service functions and CSV parser"
```

---

## Task 6: Router and Mount on FastAPI App

**Files:**
- Create: `app/dashboard_api/router.py`
- Modify: `app/webhook_receiver/main.py`

- [ ] **Step 1: Create the router**

```python
# app/dashboard_api/router.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dashboard_api import campaigns as campaign_svc
from app.dashboard_api import kpi as kpi_svc
from app.dashboard_api import leads as lead_svc
from app.dashboard_api.schemas import (
    CampaignCreate,
    CampaignOut,
    CampaignStatusPatch,
    KpiOut,
    LeadAssign,
    LeadOut,
    LeadUploadResult,
)
from app.dashboard_api.websocket import manager
from app.db.dependencies import get_db
from app.models.call import Call, CallStatus

api_router = APIRouter(prefix="/api")
ws_router = APIRouter()


# --- Campaigns ---

@api_router.get("/campaigns", response_model=list[CampaignOut])
async def get_campaigns(db: AsyncSession = Depends(get_db)):
    return await campaign_svc.list_campaigns(db)


@api_router.post("/campaigns", response_model=CampaignOut, status_code=201)
async def post_campaign(body: CampaignCreate, db: AsyncSession = Depends(get_db)):
    async with db.begin():
        return await campaign_svc.create_campaign(db, body)


@api_router.patch("/campaigns/{campaign_id}/status", response_model=CampaignOut)
async def patch_campaign(
    campaign_id: uuid.UUID,
    body: CampaignStatusPatch,
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        return await campaign_svc.patch_campaign_status(db, campaign_id, body)


# --- Leads ---

@api_router.get("/leads", response_model=list[LeadOut])
async def get_leads(
    campaign_id: uuid.UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await lead_svc.list_leads(db, campaign_id, status)


@api_router.post("/leads/upload", response_model=LeadUploadResult)
async def post_leads_upload(
    campaign_id: uuid.UUID | None = None,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    async with db.begin():
        return await lead_svc.upload_leads(db, content, campaign_id)


@api_router.post("/leads/assign")
async def post_leads_assign(body: LeadAssign, db: AsyncSession = Depends(get_db)):
    async with db.begin():
        count = await lead_svc.assign_leads(db, body)
    return {"assigned": count}


# --- Calls ---

@api_router.get("/calls/active")
async def get_active_calls(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Call).where(Call.status == CallStatus.CALLING))
    calls = result.scalars().all()
    return [
        {
            "call_id": c.retell_call_id,
            "lead_id": str(c.lead_id) if c.lead_id else None,
            "status": c.status,
            "start_time": c.start_time.isoformat() if c.start_time else None,
        }
        for c in calls
    ]


# --- KPI ---

@api_router.get("/kpi", response_model=KpiOut)
async def get_kpi(
    range: str = Query("today", pattern="^(today|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
):
    return await kpi_svc.get_kpi(db, range)


# --- WebSocket ---

@ws_router.websocket("/ws/calls")
async def ws_calls(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep connection alive; client doesn't need to send
    except WebSocketDisconnect:
        manager.disconnect(ws)
```

- [ ] **Step 2: Mount routers on the FastAPI app**

Open `app/webhook_receiver/main.py`. The current file is:
```python
# app/webhook_receiver/main.py
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from app.core.settings import settings
from app.db.session import close_db, init_session_factory
from app.webhook_receiver.router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_factory = await init_session_factory()
    app.state.session_factory = session_factory
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    yield
    await close_db()
    await app.state.redis.aclose()


app = FastAPI(title="Retell Webhook Receiver", lifespan=lifespan)
app.include_router(router)
```

Replace it with:
```python
# app/webhook_receiver/main.py
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from app.core.settings import settings
from app.db.session import close_db, init_session_factory
from app.dashboard_api.router import api_router, ws_router
from app.webhook_receiver.router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_factory = await init_session_factory()
    app.state.session_factory = session_factory
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    yield
    await close_db()
    await app.state.redis.aclose()


app = FastAPI(title="Retell Webhook Receiver", lifespan=lifespan)
app.include_router(router)
app.include_router(api_router)
app.include_router(ws_router)
```

- [ ] **Step 3: Run the full test suite to verify nothing broke**

```
pytest tests/unit/ -v
```
Expected: all 184 existing tests PASS plus the new dashboard tests (total ~215+)

- [ ] **Step 4: Commit**

```bash
git add app/dashboard_api/router.py app/webhook_receiver/main.py
git commit -m "feat: add dashboard API router and mount on FastAPI app"
```

---

## Task 7: Webhook Handler Integration

Wire `broadcast()` into the three webhook handlers so live call events reach the browser.

**Files:**
- Modify: `app/webhook_receiver/handlers/transcript_updated.py`
- Modify: `app/webhook_receiver/handlers/call_started.py`
- Modify: `app/webhook_receiver/handlers/call_ended.py`

- [ ] **Step 1: Update `transcript_updated.py`**

Replace the entire file content with:
```python
# app/webhook_receiver/handlers/transcript_updated.py
import logging

from app.dashboard_api.websocket import broadcast
from app.webhook_receiver.schemas.transcript_updated import TranscriptUpdatedPayload

logger = logging.getLogger(__name__)


async def handle_transcript_updated(payload: TranscriptUpdatedPayload) -> None:
    await broadcast({
        "event": "transcript_updated",
        "call_id": payload.call_id,
        "payload": {"transcript": payload.transcript},
    })
    logger.debug(
        "Broadcast transcript_updated",
        extra={"retell_call_id": payload.call_id},
    )
```

- [ ] **Step 2: Update `call_started.py`**

Add the broadcast call at the end of `handle_call_started`, after the `logger.info("Handled call_started", ...)` line. Add the import at the top:

```python
from app.dashboard_api.websocket import broadcast
```

Add this block at the very end of the function (after the existing `logger.info`):
```python
    await broadcast({
        "event": "call_started",
        "call_id": retell_call_id,
        "payload": {"from_number": payload.from_number},
    })
```

The full updated file:
```python
# app/webhook_receiver/handlers/call_started.py
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.dashboard_api.websocket import broadcast
from app.models.contact import ContactStatus
from app.webhook_receiver.schemas.call_started import CallStartedPayload
from app.webhook_receiver.services import call_log_service, lead_service

logger = logging.getLogger(__name__)


async def handle_call_started(
    payload: CallStartedPayload,
    session_factory: async_sessionmaker,
) -> None:
    retell_call_id = payload.call_id

    start_time = datetime.now(tz=timezone.utc)
    if payload.start_timestamp is not None:
        start_time = datetime.fromtimestamp(payload.start_timestamp / 1000, tz=timezone.utc)

    lead_id: uuid.UUID | None = None
    if payload.metadata:
        raw_id = payload.metadata.get("lead_id")
        if raw_id:
            try:
                lead_id = uuid.UUID(raw_id)
            except ValueError:
                logger.warning(
                    "Invalid lead_id in metadata — proceeding without lead_id",
                    extra={"raw_lead_id": raw_id, "retell_call_id": retell_call_id},
                )

    try:
        async with session_factory() as session:
            async with session.begin():
                call = await call_log_service.upsert_call_log(
                    session=session,
                    retell_call_id=retell_call_id,
                    start_time=start_time,
                    lead_id=lead_id,
                )
                await lead_service.set_lead_status(
                    session=session,
                    lead_id=call.lead_id,
                    status=ContactStatus.CALLING,
                )
    except ValueError as exc:
        logger.warning(
            "Cannot record call_started — no lead_id available",
            extra={"retell_call_id": retell_call_id, "error": str(exc)},
        )
        return

    logger.info("Handled call_started", extra={"retell_call_id": retell_call_id})
    await broadcast({
        "event": "call_started",
        "call_id": retell_call_id,
        "payload": {"from_number": payload.from_number},
    })
```

- [ ] **Step 3: Update `call_ended.py`**

Add the import at the top and broadcast call at the end:
```python
from app.dashboard_api.websocket import broadcast
```

The full updated file:
```python
# app/webhook_receiver/handlers/call_ended.py
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.dashboard_api.websocket import broadcast
from app.models.contact import ContactStatus
from app.webhook_receiver.config import FAILED_DISCONNECT_REASONS
from app.webhook_receiver.schemas.call_ended import CallEndedPayload
from app.webhook_receiver.services import call_log_service, lead_service

logger = logging.getLogger(__name__)


async def handle_call_ended(
    payload: CallEndedPayload,
    session_factory: async_sessionmaker,
) -> None:
    retell_call_id = payload.call_id

    end_time = datetime.now(tz=timezone.utc)
    if payload.end_timestamp is not None:
        end_time = datetime.fromtimestamp(payload.end_timestamp / 1000, tz=timezone.utc)

    duration_sec: int | None = None
    if payload.duration_ms is not None:
        duration_sec = payload.duration_ms // 1000

    if payload.disconnect_reason is None:
        logger.warning(
            "call_ended with no disconnect_reason — treating as completed",
            extra={"retell_call_id": retell_call_id},
        )
        lead_status = ContactStatus.COMPLETED
    elif payload.disconnect_reason in FAILED_DISCONNECT_REASONS:
        lead_status = ContactStatus.FAILED
    else:
        lead_status = ContactStatus.COMPLETED

    async with session_factory() as session:
        async with session.begin():
            call = await call_log_service.update_call_end(
                session=session,
                retell_call_id=retell_call_id,
                end_time=end_time,
                duration_sec=duration_sec,
                disconnect_reason=payload.disconnect_reason,
                recording_url=payload.recording_url,
            )
            if call is not None and call.lead_id is not None:
                await lead_service.set_lead_status(
                    session=session,
                    lead_id=call.lead_id,
                    status=lead_status,
                )

    logger.info(
        "Handled call_ended",
        extra={
            "retell_call_id": retell_call_id,
            "disconnect_reason": payload.disconnect_reason,
            "lead_status": lead_status.value,
        },
    )
    await broadcast({
        "event": "call_ended",
        "call_id": retell_call_id,
        "payload": {"disconnect_reason": payload.disconnect_reason},
    })
```

- [ ] **Step 4: Run the full test suite**

```
pytest tests/unit/ -v
```
Expected: all tests PASS. The existing `test_dispatcher.py` mocks `handle_transcript_updated` so the import of `broadcast` inside the handler does not affect those tests.

- [ ] **Step 5: Commit**

```bash
git add app/webhook_receiver/handlers/transcript_updated.py \
        app/webhook_receiver/handlers/call_started.py \
        app/webhook_receiver/handlers/call_ended.py
git commit -m "feat: broadcast live call events from webhook handlers"
```

---

## Task 8: Next.js Scaffold

**Files:**
- Create: `app/dashboard/package.json`
- Create: `app/dashboard/tsconfig.json`
- Create: `app/dashboard/next.config.js`
- Create: `app/dashboard/tailwind.config.js`
- Create: `app/dashboard/postcss.config.js`
- Create: `app/dashboard/app/globals.css`
- Create: `app/dashboard/app/layout.tsx`

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "dashboard",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "14.2.3",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "recharts": "^2.12.7",
    "swr": "^2.2.5"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.38",
    "tailwindcss": "^3.4.3",
    "typescript": "^5.4.5"
  }
}
```

- [ ] **Step 2: Create `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `next.config.js`**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',  // required by Dockerfile.dashboard multi-stage build
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ]
  },
}

module.exports = nextConfig
```

- [ ] **Step 4: Create `tailwind.config.js` and `postcss.config.js`**

```js
// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: { extend: {} },
  plugins: [],
}
```

```js
// postcss.config.js
module.exports = {
  plugins: { tailwindcss: {}, autoprefixer: {} },
}
```

- [ ] **Step 5: Create `app/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 6: Create `app/layout.tsx`**

```tsx
// app/dashboard/app/layout.tsx
import './globals.css'
import Link from 'next/link'
import type { Metadata } from 'next'

export const metadata: Metadata = { title: 'Voice Agent Dashboard' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-screen bg-gray-50">
        <nav className="w-48 shrink-0 bg-gray-900 text-white flex flex-col p-4 gap-3">
          <span className="text-base font-bold mb-2">Dashboard</span>
          <Link href="/" className="text-sm hover:text-gray-300">Live Monitor</Link>
          <Link href="/campaigns" className="text-sm hover:text-gray-300">Campaigns</Link>
          <Link href="/kpi" className="text-sm hover:text-gray-300">KPI</Link>
        </nav>
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </body>
    </html>
  )
}
```

- [ ] **Step 7: Install npm dependencies**

Run from the `app/dashboard/` directory:
```
cd app/dashboard && npm install
```
Expected: `node_modules/` created, no errors.

- [ ] **Step 8: Commit**

```bash
git add app/dashboard/
git commit -m "feat: scaffold Next.js 14 dashboard project"
```

---

## Task 9: Live Monitor Page

**Files:**
- Create: `app/dashboard/app/page.tsx`
- Create: `app/dashboard/components/LiveCallFeed.tsx`
- Create: `app/dashboard/components/CallCard.tsx`

- [ ] **Step 1: Create `CallCard.tsx`**

```tsx
// app/dashboard/components/CallCard.tsx
export interface CallState {
  call_id: string
  lead_id: string | null
  phone_number: string | null
  status: string
  start_time: string | null
  transcript: string
}

export default function CallCard({ call }: { call: CallState }) {
  return (
    <div className="bg-white rounded-lg shadow p-4 border-l-4 border-green-500">
      <div className="flex justify-between mb-2">
        <span className="font-mono text-sm text-gray-700">
          {call.phone_number ?? call.call_id}
        </span>
        <span className="text-xs uppercase font-semibold text-green-600">{call.status}</span>
      </div>
      <p className="text-sm text-gray-600 whitespace-pre-wrap">
        {call.transcript || 'Waiting for transcript…'}
      </p>
    </div>
  )
}
```

- [ ] **Step 2: Create `LiveCallFeed.tsx`**

```tsx
// app/dashboard/components/LiveCallFeed.tsx
'use client'

import { useEffect, useState } from 'react'
import CallCard, { type CallState } from './CallCard'

type CallMap = Record<string, CallState>

export default function LiveCallFeed() {
  const [calls, setCalls] = useState<CallMap>({})

  useEffect(() => {
    fetch('/api/calls/active')
      .then(r => r.json())
      .then((data: Omit<CallState, 'transcript'>[]) => {
        const map: CallMap = {}
        data.forEach(c => { map[c.call_id] = { ...c, transcript: '' } })
        setCalls(map)
      })
      .catch(() => {})

    const ws = new WebSocket('ws://localhost:8000/ws/calls')
    ws.onmessage = (e: MessageEvent) => {
      const msg = JSON.parse(e.data as string) as {
        event: string
        call_id: string
        payload: Record<string, string>
      }
      if (msg.event === 'call_started') {
        setCalls(prev => ({
          ...prev,
          [msg.call_id]: {
            call_id: msg.call_id,
            lead_id: null,
            phone_number: msg.payload?.from_number ?? null,
            status: 'calling',
            start_time: null,
            transcript: '',
          },
        }))
      } else if (msg.event === 'transcript_updated') {
        setCalls(prev => ({
          ...prev,
          [msg.call_id]: {
            ...(prev[msg.call_id] ?? { call_id: msg.call_id, lead_id: null, phone_number: null, status: 'calling', start_time: null, transcript: '' }),
            transcript: msg.payload?.transcript ?? '',
          },
        }))
      } else if (msg.event === 'call_ended') {
        setCalls(prev => {
          const next = { ...prev }
          delete next[msg.call_id]
          return next
        })
      }
    }
    return () => ws.close()
  }, [])

  const activeCalls = Object.values(calls)
  if (activeCalls.length === 0) {
    return <p className="text-gray-500">No active calls right now.</p>
  }
  return (
    <div className="flex flex-col gap-4">
      {activeCalls.map(c => <CallCard key={c.call_id} call={c} />)}
    </div>
  )
}
```

- [ ] **Step 3: Create `app/page.tsx`**

```tsx
// app/dashboard/app/page.tsx
import LiveCallFeed from '@/components/LiveCallFeed'

export default function LiveMonitorPage() {
  return (
    <>
      <h1 className="text-2xl font-bold mb-4">Live Monitor</h1>
      <LiveCallFeed />
    </>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add app/dashboard/app/page.tsx \
        app/dashboard/components/LiveCallFeed.tsx \
        app/dashboard/components/CallCard.tsx
git commit -m "feat: add live monitor page with WebSocket call feed"
```

---

## Task 10: Campaigns Page

**Files:**
- Create: `app/dashboard/app/campaigns/page.tsx`
- Create: `app/dashboard/components/CampaignTable.tsx`
- Create: `app/dashboard/components/CreateCampaignModal.tsx`
- Create: `app/dashboard/components/LeadUpload.tsx`

- [ ] **Step 1: Create `CreateCampaignModal.tsx`**

```tsx
// app/dashboard/components/CreateCampaignModal.tsx
'use client'

import { useState } from 'react'

const TEMPLATES = [
  { label: 'Real Estate Lead Qualifier', key: 'real_estate' },
  { label: 'Recruitment Screener', key: 'recruitment' },
  { label: 'Financial Services Qualifier', key: 'financial_services' },
]

interface Campaign {
  id: string
  name: string
  status: string
  lead_count: number
}

export default function CreateCampaignModal({
  onCreated,
  onClose,
}: {
  onCreated: (c: Campaign) => void
  onClose: () => void
}) {
  const [name, setName] = useState('')
  const [template, setTemplate] = useState(TEMPLATES[0].key)
  const [loading, setLoading] = useState(false)

  async function submit() {
    setLoading(true)
    const res = await fetch('/api/campaigns', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        prompt_template: { template_key: template },
        llm_config: {},
      }),
    })
    const data = (await res.json()) as Campaign
    onCreated(data)
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-96 shadow-xl">
        <h2 className="text-lg font-bold mb-4">New Campaign</h2>
        <label className="block text-sm font-medium mb-1">Campaign Name</label>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          className="w-full border rounded px-3 py-2 mb-4 text-sm"
          placeholder="e.g. May Real Estate Batch"
        />
        <label className="block text-sm font-medium mb-1">Template</label>
        <select
          value={template}
          onChange={e => setTemplate(e.target.value)}
          className="w-full border rounded px-3 py-2 mb-4 text-sm"
        >
          {TEMPLATES.map(t => (
            <option key={t.key} value={t.key}>{t.label}</option>
          ))}
        </select>
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border rounded hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={!name || loading}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Creating…' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create `LeadUpload.tsx`**

```tsx
// app/dashboard/components/LeadUpload.tsx
'use client'

import { useState } from 'react'

export default function LeadUpload({
  campaignId,
  onClose,
}: {
  campaignId: string
  onClose: () => void
}) {
  const [result, setResult] = useState<{ inserted: number; skipped: number } | null>(null)
  const [error, setError] = useState('')

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`/api/leads/upload?campaign_id=${campaignId}`, {
      method: 'POST',
      body: form,
    })
    if (!res.ok) {
      setError('Upload failed — check CSV format.')
      return
    }
    setResult((await res.json()) as { inserted: number; skipped: number })
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-80 shadow-xl">
        <h2 className="text-lg font-bold mb-2">Upload Leads</h2>
        <p className="text-xs text-gray-500 mb-4">
          Required columns: <code>phone_number</code>, <code>timezone</code>
          <br />Optional: <code>first_name</code>, <code>last_name</code>, <code>company</code>
        </p>
        <input type="file" accept=".csv" onChange={onFile} className="mb-3 text-sm" />
        {result && (
          <p className="text-green-700 text-sm">
            Inserted: {result.inserted} &nbsp;|&nbsp; Skipped: {result.skipped}
          </p>
        )}
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <div className="flex justify-end mt-4">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border rounded hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `CampaignTable.tsx`**

```tsx
// app/dashboard/components/CampaignTable.tsx
'use client'

import { useState } from 'react'
import CreateCampaignModal from './CreateCampaignModal'
import LeadUpload from './LeadUpload'

interface Campaign {
  id: string
  name: string
  status: string
  lead_count: number
}

export default function CampaignTable({ initialCampaigns }: { initialCampaigns: Campaign[] }) {
  const [campaigns, setCampaigns] = useState<Campaign[]>(initialCampaigns)
  const [showCreate, setShowCreate] = useState(false)
  const [uploadFor, setUploadFor] = useState<string | null>(null)

  async function patchStatus(id: string, status: string) {
    await fetch(`/api/campaigns/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
    setCampaigns(prev => prev.map(c => (c.id === id ? { ...c, status } : c)))
  }

  function onCreated(campaign: Campaign) {
    setCampaigns(prev => [...prev, campaign])
    setShowCreate(false)
  }

  return (
    <>
      <button
        onClick={() => setShowCreate(true)}
        className="mb-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
      >
        + New Campaign
      </button>

      {showCreate && (
        <CreateCampaignModal onCreated={onCreated} onClose={() => setShowCreate(false)} />
      )}

      <table className="w-full bg-white shadow rounded-lg overflow-hidden text-sm">
        <thead className="bg-gray-100 text-left">
          <tr>
            <th className="p-3">Name</th>
            <th className="p-3">Status</th>
            <th className="p-3">Leads</th>
            <th className="p-3">Actions</th>
          </tr>
        </thead>
        <tbody>
          {campaigns.map(c => (
            <tr key={c.id} className="border-t">
              <td className="p-3">{c.name}</td>
              <td className="p-3 capitalize">{c.status}</td>
              <td className="p-3">{c.lead_count}</td>
              <td className="p-3 flex gap-2 flex-wrap">
                <button
                  onClick={() => patchStatus(c.id, 'active')}
                  className="px-2 py-1 bg-green-100 text-green-700 rounded"
                >
                  Resume
                </button>
                <button
                  onClick={() => patchStatus(c.id, 'paused')}
                  className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded"
                >
                  Pause
                </button>
                <button
                  onClick={() => patchStatus(c.id, 'completed')}
                  className="px-2 py-1 bg-red-100 text-red-700 rounded"
                >
                  Stop
                </button>
                <button
                  onClick={() => setUploadFor(c.id)}
                  className="px-2 py-1 bg-blue-100 text-blue-700 rounded"
                >
                  Upload Leads
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {uploadFor && (
        <LeadUpload campaignId={uploadFor} onClose={() => setUploadFor(null)} />
      )}
    </>
  )
}
```

- [ ] **Step 4: Create `app/campaigns/page.tsx`**

```tsx
// app/dashboard/app/campaigns/page.tsx
import CampaignTable from '@/components/CampaignTable'

async function getCampaigns() {
  try {
    const res = await fetch('http://localhost:8000/api/campaigns', { cache: 'no-store' })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

export default async function CampaignsPage() {
  const campaigns = await getCampaigns()
  return (
    <>
      <h1 className="text-2xl font-bold mb-4">Campaigns</h1>
      <CampaignTable initialCampaigns={campaigns} />
    </>
  )
}
```

- [ ] **Step 5: Commit**

```bash
git add app/dashboard/app/campaigns/ \
        app/dashboard/components/CampaignTable.tsx \
        app/dashboard/components/CreateCampaignModal.tsx \
        app/dashboard/components/LeadUpload.tsx
git commit -m "feat: add campaigns page with create modal and lead upload"
```

---

## Task 11: KPI Page

**Files:**
- Create: `app/dashboard/app/kpi/page.tsx`
- Create: `app/dashboard/components/RangeSelector.tsx`
- Create: `app/dashboard/components/KpiChart.tsx`

- [ ] **Step 1: Create `RangeSelector.tsx`**

```tsx
// app/dashboard/components/RangeSelector.tsx
'use client'

import { useRouter } from 'next/navigation'

const RANGES = [
  { label: 'Today', value: 'today' },
  { label: '7 days', value: '7d' },
  { label: '30 days', value: '30d' },
]

export default function RangeSelector({ current }: { current: string }) {
  const router = useRouter()
  return (
    <div className="flex gap-2">
      {RANGES.map(r => (
        <button
          key={r.value}
          onClick={() => router.push(`/kpi?range=${r.value}`)}
          className={`px-3 py-1 rounded text-sm border transition-colors ${
            current === r.value
              ? 'bg-blue-600 text-white border-blue-600'
              : 'bg-white hover:bg-gray-50'
          }`}
        >
          {r.label}
        </button>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Create `KpiChart.tsx`**

```tsx
// app/dashboard/components/KpiChart.tsx
'use client'

import useSWR from 'swr'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'

const fetcher = (url: string) => fetch(url).then(r => r.json())

interface KpiData {
  total_leads: number
  calls_made: number
  connection_rate: number
  avg_duration_sec: number
}

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  )
}

export default function KpiChart({ range }: { range: string }) {
  const { data, isLoading } = useSWR<KpiData>(
    `/api/kpi?range=${range}`,
    fetcher,
    { refreshInterval: 30_000 },
  )

  if (isLoading) return <p className="text-gray-500">Loading…</p>
  if (!data) return null

  const chartData = [
    { name: 'Calls Made', value: data.calls_made },
    { name: 'Avg Duration (s)', value: data.avg_duration_sec },
  ]

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total Leads" value={data.total_leads} />
        <KpiCard label="Calls Made" value={data.calls_made} />
        <KpiCard label="Connection Rate" value={`${(data.connection_rate * 100).toFixed(1)}%`} />
        <KpiCard label="Avg Duration" value={`${data.avg_duration_sec}s`} />
      </div>
      <div className="bg-white rounded-lg shadow p-4">
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Area type="monotone" dataKey="value" stroke="#2563eb" fill="#dbeafe" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `app/kpi/page.tsx`**

```tsx
// app/dashboard/app/kpi/page.tsx
import KpiChart from '@/components/KpiChart'
import RangeSelector from '@/components/RangeSelector'

export default function KpiPage({
  searchParams,
}: {
  searchParams: { range?: string }
}) {
  const range = searchParams?.range ?? 'today'
  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">KPI</h1>
        <RangeSelector current={range} />
      </div>
      <KpiChart range={range} />
    </>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add app/dashboard/app/kpi/ \
        app/dashboard/components/KpiChart.tsx \
        app/dashboard/components/RangeSelector.tsx
git commit -m "feat: add KPI page with Recharts area chart and range selector"
```

---

## Task 12: Docker Compose

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
# docker-compose.yml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: agent
      POSTGRES_DB: agent_ops
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://agent:agent@db:5432/agent_ops
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - db
      - redis

  dashboard:
    build:
      context: app/dashboard
      dockerfile: Dockerfile.dashboard
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://api:8000
    depends_on:
      - api

volumes:
  pgdata:
```

- [ ] **Step 2: Create `app/dashboard/Dockerfile.dashboard`**

```dockerfile
# app/dashboard/Dockerfile.dashboard
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml app/dashboard/Dockerfile.dashboard
git commit -m "feat: add Docker Compose with dashboard service"
```

---

## Task 13: Final Test Run

- [ ] **Step 1: Run the full backend test suite**

```
pytest tests/unit/ -v
```
Expected: all tests pass. Target count: ~215 (184 existing + ~31 new dashboard tests).

- [ ] **Step 2: Verify Next.js builds without TypeScript errors**

```
cd app/dashboard && npm run build
```
Expected: build succeeds with no TypeScript errors.

- [ ] **Step 3: Commit if any last fixes were needed**

```bash
git add -p
git commit -m "fix: resolve any remaining issues from final test run"
```

---

*Spec: docs/superpowers/specs/2026-05-09-dashboard-design.md*
