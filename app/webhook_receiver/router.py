# app/webhook_receiver/router.py
import json
import logging
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.webhook_receiver.config import REPLAY_TTL_SECONDS
from app.webhook_receiver.dependencies import verified_webhook_body
from app.webhook_receiver.dispatcher import dispatch
from app.webhook_receiver.schemas import BaseRetellEvent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook")
async def webhook_endpoint(
    request: Request,
    raw_body: bytes = Depends(verified_webhook_body),
) -> JSONResponse:
    start_ts = time.monotonic()

    payload_dict = json.loads(raw_body)
    base_event = BaseRetellEvent(**payload_dict)
    event_type = base_event.event
    call_id = base_event.call_id

    # Redis replay protection
    redis = request.app.state.redis
    replay_key = f"webhook:seen:{call_id}:{event_type}"
    try:
        if await redis.exists(replay_key):
            logger.info(
                "Duplicate webhook event — skipping",
                extra={"event_type": event_type, "call_id": call_id},
            )
            return JSONResponse({"status": "ok"})
        await redis.setex(replay_key, REPLAY_TTL_SECONDS, "1")
    except Exception as exc:
        logger.warning("Redis unavailable for replay check", extra={"error": str(exc)})

    session_factory = request.app.state.session_factory
    await dispatch(base_event, payload_dict, session_factory)

    latency_ms = int((time.monotonic() - start_ts) * 1000)
    logger.info(
        "Webhook processed",
        extra={"event_type": event_type, "call_id": call_id, "processing_latency_ms": latency_ms},
    )

    return JSONResponse({"status": "ok"})
