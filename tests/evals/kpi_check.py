"""KPI reporting script — queries real DB, prints formatted KPI table, exits 1 on threshold breach.

Usage:
    python tests/evals/kpi_check.py
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import text
from app.core.settings import settings


KPI_TABLE_HEADER = f"{'KPI':<35} {'Value':>12} {'Target':>12} {'Alert':>10} {'Status':>8}"
KPI_TABLE_SEP = "-" * 80


async def _fetch_kpis(engine: AsyncEngine) -> list[dict]:
    """Run all KPI queries and return list of result dicts."""
    async with engine.connect() as conn:
        row = await conn.execute(text(
            "SELECT AVG(duration_sec) FROM agent_operations.call_logs WHERE duration_sec IS NOT NULL"
        ))
        avg_duration = row.scalar()

        row = await conn.execute(text("""
            SELECT
                COUNT(CASE WHEN structured_data IS NOT NULL THEN 1 END) * 100.0
                / NULLIF(COUNT(*), 0)
            FROM agent_operations.call_transcripts
        """))
        structured_pct = row.scalar()

        # count calls placed to numbers already in DNC registry
        row = await conn.execute(text("""
            SELECT COUNT(DISTINCT cl.id)
            FROM agent_operations.call_logs cl
            JOIN agent_operations.leads l ON cl.lead_id = l.id
            JOIN agent_operations.dnc_registry d ON l.phone_number = d.phone_number
        """))
        dnc_misses = row.scalar() or 0

        row = await conn.execute(text("""
            SELECT
                COUNT(CASE WHEN duration_sec < 10 THEN 1 END) * 100.0
                / NULLIF(COUNT(*), 0)
            FROM agent_operations.call_logs
            WHERE duration_sec IS NOT NULL
        """))
        abandon_pct = row.scalar()

    return [
        {
            "name": "Avg call duration",
            "value": f"{avg_duration:.1f}s" if avg_duration is not None else "no data",
            "target": "> 90s",
            "alert": "< 30s",
            "breached": avg_duration is not None and float(avg_duration) < 30,
        },
        {
            "name": "Structured output completion",
            "value": f"{structured_pct:.1f}%" if structured_pct is not None else "no data",
            "target": "> 95%",
            "alert": "< 85%",
            "breached": structured_pct is not None and float(structured_pct) < 85,
        },
        {
            "name": "DNC miss rate",
            "value": str(int(dnc_misses)),
            "target": "0",
            "alert": "any non-zero",
            "breached": int(dnc_misses) > 0,
        },
        {
            "name": "Call abandon rate",
            "value": f"{abandon_pct:.1f}%" if abandon_pct is not None else "no data",
            "target": "< 15%",
            "alert": "> 25%",
            "breached": abandon_pct is not None and float(abandon_pct) > 25,
        },
        {
            "name": "End-to-end response latency",
            "value": "requires instrumentation",
            "target": "< 500ms",
            "alert": "> 800ms",
            "breached": False,
        },
        {
            "name": "First-5-second detection rate",
            "value": "requires instrumentation",
            "target": "< 20%",
            "alert": "> 35%",
            "breached": False,
        },
    ]


async def main() -> int:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        kpis = await _fetch_kpis(engine)
    finally:
        await engine.dispose()

    print(KPI_TABLE_HEADER)
    print(KPI_TABLE_SEP)
    any_breach = False
    for kpi in kpis:
        status = "BREACH" if kpi["breached"] else "ok"
        if kpi["breached"]:
            any_breach = True
        print(
            f"{kpi['name']:<35} {kpi['value']:>12} {kpi['target']:>12} {kpi['alert']:>10} {status:>8}"
        )
    print(KPI_TABLE_SEP)
    if any_breach:
        print("RESULT: KPI threshold breached — see BREACH rows above")
    else:
        print("RESULT: All KPIs within thresholds")
    return 1 if any_breach else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
