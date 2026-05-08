from pydantic import BaseModel, ConfigDict


class BaseRetellEvent(BaseModel):
    event: str
    call_id: str
    timestamp: int | None = None

    model_config = ConfigDict(extra="allow")
