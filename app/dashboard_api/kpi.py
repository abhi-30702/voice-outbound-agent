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
