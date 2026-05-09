import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from app.dashboard_api.campaigns import list_campaigns, create_campaign, patch_campaign_status
from app.dashboard_api.schemas import CampaignCreate, CampaignStatusPatch


@pytest.mark.asyncio
async def test_list_campaigns_returns_list():
    db = AsyncMock()
    test_id = uuid.uuid4()
    row = MagicMock()
    row.id = test_id
    row.name = "Camp A"
    row.status = "draft"
    row.lead_count = 3
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
