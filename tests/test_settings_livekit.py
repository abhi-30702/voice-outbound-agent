import pytest
from app.core.settings import Settings


def test_livekit_fields_present():
    s = Settings(
        LIVEKIT_URL="wss://test.livekit.cloud",
        LIVEKIT_API_KEY="APIkey",
        LIVEKIT_API_SECRET="secret",
        DEEPGRAM_API_KEY="dg-key",
        GROQ_API_KEY="gsk-key",
        ELEVENLABS_API_KEY="el-key",
    )
    assert s.LIVEKIT_URL == "wss://test.livekit.cloud"
    assert s.LIVEKIT_API_KEY == "APIkey"
    assert s.LIVEKIT_API_SECRET == "secret"
    assert s.DEEPGRAM_API_KEY == "dg-key"
    assert s.GROQ_API_KEY == "gsk-key"
    assert s.ELEVENLABS_API_KEY == "el-key"


def test_retell_fields_gone():
    s = Settings.__fields__ if hasattr(Settings, "__fields__") else Settings.model_fields
    assert "RETELL_WEBHOOK_SECRET" not in s
