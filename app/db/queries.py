"""Database query helpers with parameterized queries.

All queries use bound parameters (:param_name) to prevent SQL injection.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional


async def is_phone_in_dnc(session: AsyncSession, phone_number: str) -> bool:
    """
    Check if phone number is in DNC registry using SQL-based NOT EXISTS.

    IMPORTANT: This uses parameterized queries. Do NOT use f-strings or string
    interpolation for SQL. Always use bound parameters.

    Args:
        session: AsyncSession for database access
        phone_number: Phone number in E.164 format (e.g., '+1234567890')

    Returns:
        True if phone is in DNC registry, False otherwise

    Example:
        is_dnc = await is_phone_in_dnc(session, "+919876543210")
        if is_dnc:
            print("Phone is DNC, skip dialing")
    """
    query = text("""
        SELECT EXISTS (
            SELECT 1 FROM agent_operations.dnc_registry
            WHERE phone_number = :phone_number
        )
    """)

    result = await session.execute(query, {"phone_number": phone_number})
    return result.scalar()


async def get_pending_leads_for_campaign(
    session: AsyncSession,
    campaign_id: str,
    limit: int = 100
) -> list[dict]:
    """
    Fetch pending leads for a campaign, excluding DNC numbers.

    Demonstrates:
    - Parameterized query with multiple bound parameters
    - JOIN with DNC registry using NOT EXISTS
    - ORDER BY for deterministic dialing order

    Args:
        session: AsyncSession for database access
        campaign_id: UUID of campaign
        limit: Max number of leads to return

    Returns:
        List of lead dicts with id, phone_number, timezone, custom_vars
    """
    query = text("""
        SELECT
            l.id,
            l.phone_number,
            l.timezone,
            l.custom_vars
        FROM agent_operations.leads l
        WHERE l.campaign_id = :campaign_id
          AND l.status = 'pending'
          AND NOT EXISTS (
              SELECT 1 FROM agent_operations.dnc_registry d
              WHERE d.phone_number = l.phone_number
          )
        ORDER BY l.created_at ASC
        LIMIT :limit
    """)

    result = await session.execute(
        query,
        {"campaign_id": campaign_id, "limit": limit}
    )

    rows = result.fetchall()
    return [
        {
            "id": row[0],
            "phone_number": row[1],
            "timezone": row[2],
            "custom_vars": row[3],
        }
        for row in rows
    ]


async def get_call_by_id(session: AsyncSession, call_id: str) -> Optional[dict]:
    """
    Fetch call details by ID.

    Args:
        session: AsyncSession for database access
        call_id: UUID of call

    Returns:
        Dict with call details or None if not found
    """
    query = text("""
        SELECT
            id,
            lead_id,
            retell_call_id,
            status,
            start_time,
            end_time,
            duration_sec,
            created_at
        FROM agent_operations.call_logs
        WHERE id = :call_id
    """)

    result = await session.execute(query, {"call_id": call_id})
    row = result.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "lead_id": row[1],
        "retell_call_id": row[2],
        "status": row[3],
        "start_time": row[4],
        "end_time": row[5],
        "duration_sec": row[6],
        "created_at": row[7],
    }
