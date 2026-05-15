from unittest.mock import MagicMock
from app.livekit_agent.agent import format_transcript


def make_message(role: str, content: str) -> MagicMock:
    msg = MagicMock()
    msg.role = role
    msg.content = content
    return msg


def test_format_transcript_assistant_and_user():
    messages = [
        make_message("system", "You are a sales agent."),
        make_message("assistant", "Hello, is this John?"),
        make_message("user", "Yes, this is John."),
        make_message("assistant", "Great, calling about solar panels."),
    ]
    result = format_transcript(messages)
    assert "Agent: Hello, is this John?" in result
    assert "User: Yes, this is John." in result
    assert "Agent: Great, calling about solar panels." in result
    assert "system" not in result.lower()


def test_format_transcript_empty():
    assert format_transcript([]) == ""
