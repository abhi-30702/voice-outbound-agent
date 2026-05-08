from .base import BaseRetellEvent


class CallEndedPayload(BaseRetellEvent):
    end_timestamp: int | None = None  # milliseconds since epoch
    duration_ms: int | None = None
    disconnect_reason: str | None = None
    recording_url: str | None = None
