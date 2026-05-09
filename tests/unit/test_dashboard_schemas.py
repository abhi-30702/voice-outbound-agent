import pytest
import uuid
from pydantic import ValidationError
from app.dashboard_api.schemas import (
    CampaignOut, CampaignCreate, CampaignStatusPatch,
    LeadOut, LeadUploadResult, LeadAssign, KpiOut, ActiveCall,
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


def test_active_call_serializes():
    import uuid
    from datetime import datetime, timezone
    ac = ActiveCall(call_id="call_123", lead_id=uuid.uuid4(), status="calling", start_time=datetime.now(tz=timezone.utc))
    d = ac.model_dump()
    assert d["call_id"] == "call_123"
    assert d["status"] == "calling"
