"""Contact/Lead model for outbound dialing."""

from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, Index, DateTime, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum as PyEnum
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin
from uuid import UUID


class ContactStatus(str, PyEnum):
    """Contact/lead status enumeration."""

    PENDING = "pending"
    CALLING = "calling"
    COMPLETED = "completed"
    FAILED = "failed"
    FAILED_DNC = "failed_dnc"


class Contact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Lead/contact entity for outbound dialing."""

    __tablename__ = "contacts"
    __table_args__ = (
        Index("idx_contact_phone", "phone_number"),
        Index("idx_contact_campaign", "campaign_id"),
        Index("idx_contact_status", "status"),
        Index("idx_contact_created", "created_at"),
        {"schema": "agent_operations"},
    )

    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    company: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    campaign_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_operations.campaigns.id"),
        nullable=True,
    )
    status: Mapped[ContactStatus] = mapped_column(
        Enum(ContactStatus),
        default=ContactStatus.PENDING,
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    custom_vars: Mapped[dict | None] = mapped_column(JSONB)
