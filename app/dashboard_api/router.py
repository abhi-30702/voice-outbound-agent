from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
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
    try:
        async with db.begin():
            return await campaign_svc.patch_campaign_status(db, campaign_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# --- Leads ---

@api_router.get("/leads", response_model=list[LeadOut])
async def get_leads(
    campaign_id: uuid.UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if status is not None:
        from app.models.contact import ContactStatus
        valid = {s.value for s in ContactStatus}
        if status not in valid:
            raise HTTPException(status_code=422, detail=f"Invalid status '{status}'. Valid values: {sorted(valid)}")
    return await lead_svc.list_leads(db, campaign_id, status)


@api_router.post("/leads/upload", response_model=LeadUploadResult)
async def post_leads_upload(
    campaign_id: uuid.UUID | None = None,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    try:
        async with db.begin():
            return await lead_svc.upload_leads(db, content, campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
