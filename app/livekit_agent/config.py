from pydantic_settings import BaseSettings
from pydantic import Field


class LiveKitAgentSettings(BaseSettings):
    LIVEKIT_URL: str = Field(default="")
    LIVEKIT_API_KEY: str = Field(default="")
    LIVEKIT_API_SECRET: str = Field(default="")
    DEEPGRAM_API_KEY: str = Field(default="")
    GROQ_API_KEY: str = Field(default="")
    ELEVENLABS_API_KEY: str = Field(default="")
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/voice_agent"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


agent_settings = LiveKitAgentSettings()
