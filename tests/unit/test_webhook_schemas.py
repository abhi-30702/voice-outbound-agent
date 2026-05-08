import pytest
from pydantic import ValidationError
from app.webhook_receiver.schemas import (
    BaseRetellEvent,
    CallStartedPayload,
    CallEndedPayload,
    CallAnalyzedPayload,
    TranscriptUpdatedPayload,
)


class TestBaseRetellEvent:
    def test_parses_required_fields(self):
        e = BaseRetellEvent(event="call_started", call_id="abc123")
        assert e.event == "call_started"
        assert e.call_id == "abc123"

    def test_missing_event_raises(self):
        with pytest.raises(ValidationError):
            BaseRetellEvent(call_id="abc")

    def test_missing_call_id_raises(self):
        with pytest.raises(ValidationError):
            BaseRetellEvent(event="call_started")

    def test_extra_fields_allowed(self):
        e = BaseRetellEvent(event="call_started", call_id="abc", unknown_field="ignored")
        assert e.call_id == "abc"

    def test_timestamp_optional(self):
        e = BaseRetellEvent(event="call_started", call_id="abc")
        assert e.timestamp is None


class TestCallStartedPayload:
    def test_parses_full_payload(self):
        p = CallStartedPayload(
            event="call_started",
            call_id="call_001",
            from_number="+11234567890",
            to_number="+10987654321",
            agent_id="agent_abc",
            start_timestamp=1746700000000,
            metadata={"lead_id": "uuid-here"},
        )
        assert p.call_id == "call_001"
        assert p.metadata == {"lead_id": "uuid-here"}

    def test_all_fields_optional_except_base(self):
        p = CallStartedPayload(event="call_started", call_id="c1")
        assert p.from_number is None
        assert p.metadata is None


class TestCallEndedPayload:
    def test_parses_full_payload(self):
        p = CallEndedPayload(
            event="call_ended",
            call_id="call_001",
            end_timestamp=1746700060000,
            duration_ms=60000,
            disconnect_reason="user_hangup",
            recording_url="https://cdn.retell.ai/rec.mp3",
        )
        assert p.duration_ms == 60000
        assert p.disconnect_reason == "user_hangup"

    def test_all_fields_optional(self):
        p = CallEndedPayload(event="call_ended", call_id="c1")
        assert p.duration_ms is None
        assert p.disconnect_reason is None


class TestCallAnalyzedPayload:
    def test_parses_transcript(self):
        p = CallAnalyzedPayload(
            event="call_analyzed",
            call_id="c1",
            transcript="Agent: Hi\nUser: Hello",
        )
        assert "Agent" in p.transcript

    def test_transcript_optional(self):
        p = CallAnalyzedPayload(event="call_analyzed", call_id="c1")
        assert p.transcript is None


class TestTranscriptUpdatedPayload:
    def test_parses_basic(self):
        p = TranscriptUpdatedPayload(
            event="transcript_updated",
            call_id="c1",
            transcript="partial...",
        )
        assert p.call_id == "c1"
