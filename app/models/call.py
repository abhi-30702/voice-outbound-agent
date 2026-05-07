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

    __tablename__ = "calls"
    __table_args__ = (
        Index("idx_call_contact", "contact_id"),
        Index("idx_call_status", "status"),
        Index("idx_call_created", "created_at"),
        {"schema": "agent_operations"},
    )

    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_operations.contacts.id"),
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
