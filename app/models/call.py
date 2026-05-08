"""Call model for tracking outbound calls."""

from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, Index, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum as PyEnum
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin
from uuid import UUID


class CallStatus(str, PyEnum):
    """Call status enumeration."""

    PENDING = "pending"
    CALLING = "calling"
    COMPLETED = "completed"
    FAILED = "failed"


class Call(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Call log entity for tracking outbound calls."""

    __tablename__ = "call_logs"
    __table_args__ = (
        Index("idx_call_log_lead", "lead_id"),
        Index("idx_call_log_status", "status"),
        Index("idx_call_log_created", "created_at"),
        {"schema": "agent_operations"},
    )

    lead_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_operations.leads.id"),
        nullable=False,
    )
    retell_call_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[CallStatus] = mapped_column(
        Enum(CallStatus),
        default=CallStatus.PENDING,
        nullable=False,
    )
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    disconnect_reason: Mapped[str | None] = mapped_column(String(100))
    recording_url: Mapped[str | None] = mapped_column(String(500))
