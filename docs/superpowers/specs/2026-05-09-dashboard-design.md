# Dashboard Design

**Date:** 2026-05-09
**Module:** 7 (dashboard)
**Status:** Approved

---

## 1. Goal

Build a Next.js 14 dashboard that gives campaign operators a live view of active calls, a campaign manager, and KPI charts. The dashboard connects to the existing FastAPI backend via REST and WebSocket. A new `app/dashboard_api/` FastAPI module handles all dashboard-specific endpoints. No new database tables are required.

---

## 2. Architecture Overview

Two services, two ports, one Docker Compose network:

- **`app/dashboard_api/`** — new FastAPI APIRouter module mounted on the existing FastAPI app (port 8000). Provides REST endpoints and a WebSocket endpoint for live call events.
- **`app/dashboard/`** — Next.js 14 App Router on port 3000. Three routes: `/` (live monitor), `/campaigns`, `/kpi`.

The existing `app/webhook_receiver/handlers.py` calls `dashboard_api.websocket.broadcast()` after processing each Retell AI event. This is a one-way dependency: webhook receiver → dashboard API, never the reverse. If no WebSocket clients are connected, `broadcast()` is a no-op.

Server components handle static/aggregated data. Client components own WebSocket connections and interactive state. All DB access uses the existing asyncpg pool with parameterised queries.

```
Retell AI → POST /webhook → webhook_receiver → dashboard_api.websocket.broadcast()
                                                          │
                                              WebSocket /ws/calls
                                                          │
                                                    browser (LiveCallFeed.tsx)
```

---

## 3. Backend Module — `app/dashboard_api/`

### File structure

```
app/dashboard_api/
├── __init__.py
├── router.py       # registers all sub-routers, mounts on main FastAPI app
├── websocket.py    # ConnectionManager class + /ws/calls endpoint
├── campaigns.py    # campaign CRUD endpoints
├── leads.py        # lead list, CSV upload, assign-to-campaign
├── kpi.py          # aggregated KPI queries
└── schemas.py      # Pydantic response models (read-only, dashboard only)
```

### REST endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/campaigns` | List all campaigns (id, name, status, lead count) |
| `POST` | `/api/campaigns` | Create campaign from template picker |
| `PATCH` | `/api/campaigns/{id}/status` | pause / resume / stop |
| `GET` | `/api/leads` | List leads (`?campaign_id=&status=`) |
| `POST` | `/api/leads/upload` | CSV upload → bulk insert |
| `POST` | `/api/leads/assign` | Assign existing lead IDs to a campaign |
| `GET` | `/api/calls/active` | Snapshot of in-progress calls (initial page load) |
| `GET` | `/api/kpi` | Aggregated metrics (`?range=today\|7d\|30d`) |

### WebSocket (`/ws/calls`)

`ConnectionManager` holds a `set` of active WebSocket connections and exposes `broadcast(message: dict)` — a coroutine that sends JSON to all connected clients, silently skipping any that have disconnected.

On connect, the server immediately pushes the current active-calls snapshot so clients don't need a separate REST call on reconnect.

**Message envelope:**
```json
{"event": "call_started|transcript_updated|call_ended", "call_id": "...", "payload": {...}}
```

---

## 4. Frontend — `app/dashboard/` (Next.js 14)

### Directory structure

```
app/dashboard/
├── package.json
├── next.config.js
├── tailwind.config.js
├── app/
│   ├── layout.tsx              # root layout: nav sidebar + page slot
│   ├── page.tsx                # /  → live monitor (client component)
│   ├── campaigns/
│   │   └── page.tsx            # /campaigns → campaign list + create modal
│   └── kpi/
│       └── page.tsx            # /kpi → KPI charts (server component, SWR refresh)
└── components/
    ├── LiveCallFeed.tsx         # WebSocket consumer, call card list
    ├── CallCard.tsx             # single call: caller name, status, live transcript
    ├── CampaignTable.tsx        # sortable list, pause/resume/stop actions
    ├── CreateCampaignModal.tsx  # template picker + name input
    ├── LeadUpload.tsx           # CSV drag-drop + assign-existing UI
    ├── KpiChart.tsx             # Recharts AreaChart wrapper
    └── RangeSelector.tsx        # today / 7d / 30d toggle
```

### Component boundaries

| Component | Type | Reason |
|-----------|------|--------|
| `kpi/page.tsx` | Server | fetches from FastAPI on render; client revalidates with SWR |
| `campaigns/page.tsx` | Server shell + client modal | list is static; create/pause actions need interactivity |
| `LiveCallFeed.tsx` | Client | owns the WebSocket connection |
| `KpiChart.tsx` | Client | Recharts requires DOM |

### WebSocket flow in `LiveCallFeed.tsx`

1. On mount: `GET /api/calls/active` → seed local state
2. Open `ws://localhost:8000/ws/calls`
3. On message: patch local state by `call_id` (update transcript; remove entry on `call_ended`)
4. On unmount: close socket

### Styling

Tailwind CSS only — no component library. Keeps bundle small and avoids version conflicts.

---

## 5. Data Flow

### Live call feed (WebSocket)

```
Retell AI
    │  POST /webhook
    ▼
app/webhook_receiver/handlers.py
    │  verify HMAC, write to DB
    │  call dashboard_api.websocket.broadcast({"event": ..., "call_id": ..., "payload": ...})
    ▼
app/dashboard_api/websocket.py  ─── ConnectionManager.broadcast()
    │  iterate active WS connections, send JSON
    ▼
browser  ─── LiveCallFeed.tsx  onmessage handler
    │  patch React state by call_id
    ▼
CallCard re-renders with new transcript line
```

### KPI and campaign data (REST + SWR)

```
browser (SWR polling, 30s interval)
    │  GET /api/kpi?range=today
    ▼
app/dashboard_api/kpi.py
    │  parameterised SQL aggregate over calls + leads tables
    ▼
JSON response → KpiChart.tsx re-renders
```

### CSV upload

```
browser  ─── LeadUpload.tsx  multipart/form-data POST
    ▼
app/dashboard_api/leads.py
    │  parse with stdlib csv module
    │  bulk INSERT into leads (parameterised)
    │  return {inserted: N, skipped: M}
    ▼
browser shows result toast
```

---

## 6. Testing Strategy

Backend only (pytest + pytest-asyncio). No frontend automated tests — manual verification for Next.js components.

| Test file | Coverage |
|-----------|----------|
| `tests/unit/test_dashboard_schemas.py` | Pydantic models serialize correctly; required fields present |
| `tests/unit/test_dashboard_kpi.py` | KPI query functions return correct shape with mock DB rows |
| `tests/unit/test_dashboard_campaigns.py` | Create/list/patch endpoints: correct status codes and payloads (mock DB) |
| `tests/unit/test_dashboard_leads.py` | CSV parser handles valid CSV, empty file, missing columns; assign endpoint validates input |
| `tests/unit/test_dashboard_websocket.py` | ConnectionManager: connect adds, disconnect removes, broadcast sends to all, skips disconnected |

**WebSocket test approach** — FastAPI `TestClient` with httpx WebSocket support:
```python
def test_broadcast_reaches_connected_client():
    with client.websocket_connect("/ws/calls") as ws:
        asyncio.run(manager.broadcast({"event": "call_started", "call_id": "abc"}))
        data = ws.receive_json()
        assert data["call_id"] == "abc"
```

**Not tested in this module:**
- Next.js components (no Jest, no Playwright)
- End-to-end Retell AI webhook → browser (integration testing, later session)
- CSV files > 10k rows (out of scope)

**Target:** ~25–30 new tests, total suite ~210–215.

---

## 7. Dependency Notes

- `app/webhook_receiver/handlers.py` imports `from app.dashboard_api.websocket import broadcast` — one-way dependency only
- No new pip packages for backend (asyncpg pool already exists; WebSocket support is in FastAPI/Starlette)
- New npm packages: `recharts`, `swr` — both stable, well-maintained
- Docker Compose: add `dashboard` service (`node:20-alpine`, port 3000, depends on `api`)

---

*Owner: Srinivas / Fidelitus Corp + SherpaVector*
