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
    db.add = MagicMock()
    db.flush = AsyncMock()
    content = b"phone_number,timezone\n+91999,Asia/Kolkata\n+91888,Asia/Kolkata\n"
    result = await upload_leads(db, content)
    assert result.inserted == 2
    assert result.skipped == 0
    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_upload_leads_reports_skipped_count():
    db = AsyncMock()
    db.add = MagicMock()
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
