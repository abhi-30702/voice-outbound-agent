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
