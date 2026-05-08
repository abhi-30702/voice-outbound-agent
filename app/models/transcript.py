"""Transcript model for call transcripts and structured extraction results."""

from sqlalchemy import String, ForeignKey, Index, Text, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum as PyEnum
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin
from uuid import UUID


class SentimentLevel(str, PyEnum):
    """Sentiment enumeration."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Transcript(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Call transcript and structured extraction results."""

    __tablename__ = "call_transcripts"
    __table_args__ = (
        Index("idx_transcript_call", "call_id"),
        {"schema": "agent_operations"},
    )

    call_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_operations.call_logs.id"),
        nullable=False,
        unique=True,
    )
    raw_transcript: Mapped[str | None] = mapped_column(Text)
    structured_data: Mapped[dict | None] = mapped_column(JSONB)
    sentiment: Mapped[SentimentLevel | None] = mapped_column(Enum(SentimentLevel))
