import logging
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from livekit.api.webhook import WebhookEvent

from app.webhook_receiver.dependencies import verified_livekit_event
from app.webhook_receiver.dispatcher import dispatch

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook/livekit")
async def livekit_webhook_endpoint(
    request: Request,
    event: WebhookEvent = Depends(verified_livekit_event),
) -> JSONResponse:
    start_ts = time.monotonic()
    session_factory = request.app.state.session_factory
    await dispatch(event, session_factory)
    latency_ms = int((time.monotonic() - start_ts) * 1000)
    logger.info(
        "LiveKit webhook processed",
        extra={"event_type": event.event, "latency_ms": latency_ms},
    )
    return JSONResponse({"status": "ok"})
