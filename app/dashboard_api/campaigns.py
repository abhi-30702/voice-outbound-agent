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
