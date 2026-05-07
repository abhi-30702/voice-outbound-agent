"""DNC Entry model for Do-Not-Call registry."""

from datetime import datetime
from sqlalchemy import String, Index, Enum
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum as PyEnum
from app.db.base import Base, UUIDPrimaryKeyMixin
from uuid import UUID


class DNCSource(str, PyEnum):
    """DNC registry source enumeration."""

    MANUAL = "manual"
    NATIONAL_DNC = "national_dnc"
    CALLER_REQUEST = "caller_request"


class DNCEntry(Base, UUIDPrimaryKeyMixin):
    """Do-Not-Call registry entry for compliance."""

    __tablename__ = "dnc_registry"
    __table_args__ = (
        Index("idx_dnc_phone", "phone_number", unique=True),
        {"schema": "agent_operations"},
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
    )
    source: Mapped[DNCSource | None] = mapped_column(Enum(DNCSource))
    added_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        nullable=False,
    )
