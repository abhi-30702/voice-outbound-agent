import logging
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/voice_agent",
    )
    SQLALCHEMY_ECHO: bool = Field(default=False)
    POOL_SIZE: int = Field(default=10)
    MAX_OVERFLOW: int = Field(default=20)
    REDIS_URL: str = Field(default="redis://localhost:6379")
    WEBHOOK_PORT: int = Field(default=8000)
    ANTHROPIC_API_KEY: str = Field(default="")
    N8N_WEBHOOK_URL: str = Field(default="")
    N8N_WEBHOOK_SECRET: str = Field(default="")

    # LiveKit
    LIVEKIT_URL: str = Field(default="")
    LIVEKIT_API_KEY: str = Field(default="")
    LIVEKIT_API_SECRET: str = Field(default="")

    # AI providers
    DEEPGRAM_API_KEY: str = Field(default="")
    GROQ_API_KEY: str = Field(default="")
    ELEVENLABS_API_KEY: str = Field(default="")

    @model_validator(mode="after")
    def warn_if_secrets_empty(self) -> "Settings":
        for field, label in [
            (self.LIVEKIT_API_KEY, "LIVEKIT_API_KEY"),
            (self.LIVEKIT_API_SECRET, "LIVEKIT_API_SECRET"),
            (self.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY"),
        ]:
            if not field:
                _logger.warning("%s is not set", label)
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
