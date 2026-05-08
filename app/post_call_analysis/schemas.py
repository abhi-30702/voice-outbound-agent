from typing import Literal
from pydantic import BaseModel


class ExtractionResult(BaseModel):
    call_outcome: Literal[
        "interested",
        "not_interested",
        "callback_requested",
        "dnc_request",
        "no_answer",
        "other",
    ]
    callback_time: str | None
    objections_raised: list[str]
    next_action: str
    summary: str
    sentiment_reason: str
    lead_temperature: Literal["hot", "warm", "cold"]
    sentiment: Literal["positive", "neutral", "negative"]
    dnc_requested: bool
