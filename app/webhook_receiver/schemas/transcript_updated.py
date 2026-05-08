from .base import BaseRetellEvent


class TranscriptUpdatedPayload(BaseRetellEvent):
    transcript: str | None = None
