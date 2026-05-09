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
