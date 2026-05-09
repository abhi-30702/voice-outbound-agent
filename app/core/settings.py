# app/core/settings.py
import logging
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/voice_agent",
        description="PostgreSQL async connection string"
    )
    SQLALCHEMY_ECHO: bool = Field(
        default=False,
        description="Log all SQL statements if True"
    )
    POOL_SIZE: int = Field(
        default=10,
        description="SQLAlchemy connection pool size"
    )
    MAX_OVERFLOW: int = Field(
        default=20,
        description="SQLAlchemy max overflow connections"
    )
    RETELL_WEBHOOK_SECRET: str = Field(
        default="",
        description="Retell AI webhook signing secret for HMAC-SHA256 verification — MUST be set in production"
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL for replay protection and RQ queue"
    )
    WEBHOOK_PORT: int = Field(
        default=8001,
        description="Port for the webhook receiver FastAPI app"
    )
    ANTHROPIC_API_KEY: str = Field(
        default="",
        description="Anthropic API key for Claude Sonnet post-call analysis — MUST be set in production"
    )
    N8N_WEBHOOK_URL: str = Field(
        default="",
        description="n8n webhook URL for post-call automation — empty string disables automation"
    )
    N8N_WEBHOOK_SECRET: str = Field(
        default="",
        description="Shared secret sent in X-Internal-Webhook-Secret header to n8n"
    )

    @model_validator(mode="after")
    def warn_if_secrets_empty(self) -> "Settings":
        if not self.RETELL_WEBHOOK_SECRET:
            _logger.warning(
                "RETELL_WEBHOOK_SECRET is not set — webhook signature verification will fail in production"
            )
        if not self.ANTHROPIC_API_KEY:
            _logger.warning(
                "ANTHROPIC_API_KEY is not set — post-call analysis will fail in production"
            )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
