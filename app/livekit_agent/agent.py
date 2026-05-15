"""LiveKit Agent worker: Deepgram STT -> Groq LLM -> ElevenLabs TTS pipeline."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import deepgram, elevenlabs
from livekit.plugins import openai as lk_openai
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.livekit_agent.config import agent_settings
from app.models.call import Call
from app.webhook_receiver.services.transcript_service import create_transcript

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a friendly outbound sales agent qualifying leads for solar panel installations.
Your goal: determine if the lead is a homeowner with an electric bill over $100/month.
Keep responses brief — under 12 words per sentence. Wait for the lead to finish speaking.
Start with: Hello, am I speaking with {first_name}?"""


def format_transcript(messages: list[Any]) -> str:
    """Convert chat history messages to a readable transcript string.

    Accepts any objects with .role and .content/.text_content attributes,
    or MagicMock objects used in tests. Skips system/developer messages.
    """
    parts = []
    for msg in messages:
        role = msg.role
        if role in ("system", "developer"):
            continue
        # Prefer text_content (real SDK ChatMessage); fall back to str(content)
        if hasattr(msg, "text_content") and not callable(msg.text_content):
            content = str(msg.text_content)
        else:
            raw = msg.content
            content = raw if isinstance(raw, str) else str(raw)
        if role == "assistant":
            parts.append(f"Agent: {content}")
        elif role == "user":
            parts.append(f"User: {content}")
    return "\n".join(parts)


class SalesAgent(Agent):
    """Outbound sales agent that qualifies leads for solar panel installations."""

    def __init__(self, system_prompt: str) -> None:
        super().__init__(instructions=system_prompt)


async def _save_transcript(room_name: str, transcript_text: str) -> None:
    """Write the call transcript to the DB after the call ends."""
    engine = create_async_engine(agent_settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db_session:
        async with db_session.begin():
            result = await db_session.execute(
                sa.select(Call).where(Call.retell_call_id == room_name)
            )
            call = result.scalar_one_or_none()
            if call is None:
                logger.warning("No call_log found for room %s", room_name)
                return

            call.end_time = datetime.now(tz=timezone.utc)
            await create_transcript(
                session=db_session,
                call_id=call.id,
                raw_transcript=transcript_text,
            )

    await engine.dispose()
    logger.info("Transcript saved for room %s", room_name)


async def entrypoint(ctx: JobContext) -> None:
    """LiveKit agent entrypoint — joins room, runs STT/LLM/TTS, saves transcript."""
    await ctx.connect()

    metadata: dict = {}
    if ctx.room.metadata:
        try:
            metadata = json.loads(ctx.room.metadata)
        except json.JSONDecodeError:
            logger.warning(
                "Could not parse room metadata for room %s", ctx.room.name
            )

    first_name = metadata.get("first_name", "there")
    system_prompt = SYSTEM_PROMPT.format(first_name=first_name)

    # Groq does not have a dedicated plugin — use OpenAI-compatible base_url
    llm = lk_openai.LLM(
        base_url="https://api.groq.com/openai/v1",
        api_key=agent_settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
    )

    session = AgentSession(
        stt=deepgram.STT(
            api_key=agent_settings.DEEPGRAM_API_KEY,
            model="nova-2",
        ),
        llm=llm,
        tts=elevenlabs.TTS(api_key=agent_settings.ELEVENLABS_API_KEY),
    )

    # start() takes agent as first positional arg; room is passed as keyword arg
    await session.start(SalesAgent(system_prompt), room=ctx.room)

    # wait_for_inactive() is the v1.5.x equivalent of wait_for_completion()
    await session.wait_for_inactive()

    # history is a property returning ChatContext; messages() is a method
    chat_ctx = session.history
    transcript_text = format_transcript(chat_ctx.messages())
    await _save_transcript(ctx.room.name, transcript_text)
