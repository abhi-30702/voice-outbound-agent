import asyncio
import logging
import uuid
from datetime import datetime, timezone

import anthropic
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from rq import get_current_job

from app.core.settings import settings
from app.db.session import init_session_factory
from app.models.call import Call
from app.models.contact import Contact, ContactStatus
from app.models.dnc_entry import DNCEntry, DNCSource
from app.models.transcript import Transcript, SentimentLevel
from app.post_call_analysis.dnc_keywords import scan
from app.post_call_analysis.prompts import SYSTEM_PROMPT, build_user_message
from app.post_call_analysis.schemas import ExtractionResult

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-6"


def _call_claude(raw_transcript: str) -> ExtractionResult:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    schema = ExtractionResult.model_json_schema()
    schema.pop("title", None)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(raw_transcript)}],
        tools=[{
            "name": "extract_call_data",
            "description": "Extract structured data from a call transcript for sales analytics",
            "input_schema": schema,
        }],
        tool_choice={"type": "any"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return ExtractionResult(**block.input)

    raise ValueError(
        f"Claude did not return a tool_use block; stop_reason={response.stop_reason}"
    )


async def _write_failure_flag(call_id_str: str, exc: Exception) -> None:
    try:
        call_id = uuid.UUID(call_id_str)
        session_factory = await init_session_factory()
        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    sa.update(Transcript)
                    .where(Transcript.call_id == call_id)
                    .values(structured_data={
                        "failed_analysis": True,
                        "error": str(exc),
                        "failed_at": datetime.now(tz=timezone.utc).isoformat(),
                    })
                )
        logger.error(
            "analyze_call exhausted all retries — dead-letter flag written",
            extra={"call_id": call_id_str, "error": str(exc)},
        )
    except Exception as write_exc:
        logger.error(
            "Failed to write dead-letter flag",
            extra={"call_id": call_id_str, "error": str(write_exc)},
        )


async def _run_analysis(call_id_str: str) -> None:
    call_id = uuid.UUID(call_id_str)
    session_factory = await init_session_factory()

    async with session_factory() as session:
        result = await session.execute(
            sa.select(Transcript).where(Transcript.call_id == call_id)
        )
        transcript = result.scalar_one_or_none()

        if transcript is None:
            logger.error("Transcript not found", extra={"call_id": call_id_str})
            return

        call_result = await session.execute(
            sa.select(Call).where(Call.id == transcript.call_id)
        )
        call = call_result.scalar_one_or_none()

        lead_phone: str | None = None
        lead_id: uuid.UUID | None = None

        if call is not None:
            lead_result = await session.execute(
                sa.select(Contact).where(Contact.id == call.lead_id)
            )
            lead = lead_result.scalar_one_or_none()
            if lead is not None:
                lead_phone = lead.phone_number
                lead_id = lead.id

    raw = transcript.raw_transcript or ""

    extraction = _call_claude(raw)

    dnc_requested = extraction.dnc_requested or scan(raw)

    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                sa.update(Transcript)
                .where(Transcript.call_id == call_id)
                .values(
                    structured_data=extraction.model_dump(),
                    sentiment=SentimentLevel[extraction.sentiment.upper()],
                )
            )

            if dnc_requested and lead_phone and lead_id:
                await session.execute(
                    pg_insert(DNCEntry)
                    .values(phone_number=lead_phone, source=DNCSource.CALLER_REQUEST)
                    .on_conflict_do_nothing(index_elements=["phone_number"])
                )
                await session.execute(
                    sa.update(Contact)
                    .where(Contact.id == lead_id)
                    .values(status=ContactStatus.FAILED_DNC)
                )

    logger.info(
        "analyze_call complete",
        extra={"call_id": call_id_str, "dnc_requested": dnc_requested},
    )


def analyze_call(call_id: str) -> None:
    try:
        asyncio.run(_run_analysis(call_id))
    except Exception as exc:
        job = get_current_job()
        if job is not None and getattr(job, "retries_left", 1) == 0:
            asyncio.run(_write_failure_flag(call_id, exc))
        raise
