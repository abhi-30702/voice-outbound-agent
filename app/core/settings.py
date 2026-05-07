# app/core/settings.py
from pydantic_settings import BaseSettings
from pydantic import Field


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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
