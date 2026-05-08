"""Campaign model for outbound call campaigns."""

from sqlalchemy import String, Enum, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum as PyEnum
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class CampaignStatus(str, PyEnum):
    """Campaign status enumeration."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Campaign entity for outbound calls."""

    __tablename__ = "campaigns"
    __table_args__ = (
        Index("idx_campaign_status", "status"),
        {"schema": "agent_operations"},
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus),
        default=CampaignStatus.DRAFT,
        nullable=False,
    )
    prompt_template: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict
    )
    llm_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict
    )
