import pytest
from unittest.mock import AsyncMock, MagicMock
from app.dashboard_api.kpi import get_kpi
from app.dashboard_api.schemas import KpiOut


def _db_with_scalars(*values):
    """Build an AsyncMock db whose execute() returns scalar_one() for each value in order."""
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one=MagicMock(return_value=v)) for v in values
    ]
    return db


@pytest.mark.asyncio
async def test_get_kpi_today_returns_kpi_out():
    db = _db_with_scalars(200, 50, 35, 45.0)
    result = await get_kpi(db, "today")
    assert isinstance(result, KpiOut)
    assert result.total_leads == 200
    assert result.calls_made == 50
    assert result.connection_rate == round(35 / 50, 4)


@pytest.mark.asyncio
async def test_get_kpi_zero_calls_gives_zero_rate_and_duration():
    db = _db_with_scalars(100, 0, 0, None)
    result = await get_kpi(db, "today")
    assert result.connection_rate == 0.0
    assert result.avg_duration_sec == 0.0


@pytest.mark.asyncio
async def test_get_kpi_7d_runs_four_queries():
    db = _db_with_scalars(0, 0, 0, None)
    await get_kpi(db, "7d")
    assert db.execute.call_count == 4


@pytest.mark.asyncio
async def test_get_kpi_30d_runs_four_queries():
    db = _db_with_scalars(0, 0, 0, None)
    await get_kpi(db, "30d")
    assert db.execute.call_count == 4


@pytest.mark.asyncio
async def test_get_kpi_connection_rate_rounds_to_four_decimals():
    db = _db_with_scalars(100, 3, 1, 60.0)
    result = await get_kpi(db, "today")
    assert result.connection_rate == round(1 / 3, 4)
