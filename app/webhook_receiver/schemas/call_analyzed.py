from .base import BaseRetellEvent


class CallAnalyzedPayload(BaseRetellEvent):
    transcript: str | None = None
