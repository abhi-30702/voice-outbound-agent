import logging

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dialing_worker.retell_client import RetellClient
from app.models.campaign import Campaign

logger = logging.getLogger(__name__)


def build_agent_payload(campaign: Campaign) -> dict:
    pt = campaign.prompt_template or {}
    lc = campaign.llm_config or {}
    return {
        "agent_name": campaign.name,
        "voice_id": lc.get("voice_id", ""),
        "response_engine": {
            "type": "retell-llm",
            "system_prompt": pt.get("system_prompt", ""),
        },
        "language": lc.get("language", "en-US"),
        "ambient_sound": lc.get("ambient_sound", None),
        "max_call_duration_ms": lc.get("max_call_duration_ms", 600_000),
    }


async def sync_agent(
    campaign: Campaign,
    client: RetellClient,
    db: AsyncSession,
) -> str:
    payload = build_agent_payload(campaign)
    lc = campaign.llm_config or {}
    existing_id = lc.get("retell_agent_id")

    if existing_id:
        await client.update_agent(existing_id, payload)
        return existing_id

    result = await client.create_agent(payload)
    agent_id = result["agent_id"]
    try:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == campaign.id)
            .values(llm_config={**lc, "retell_agent_id": agent_id})
        )
        await db.commit()
    except Exception:
        logger.error(
            "Retell agent created (agent_id=%s) but DB write failed — "
            "manually set retell_agent_id in campaign.llm_config to recover",
            agent_id,
        )
        raise
    return agent_id
