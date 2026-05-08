from .base import BaseRetellEvent


class CallStartedPayload(BaseRetellEvent):
    from_number: str | None = None
    to_number: str | None = None
    agent_id: str | None = None
    metadata: dict | None = None
    start_timestamp: int | None = None  # milliseconds since epoch
