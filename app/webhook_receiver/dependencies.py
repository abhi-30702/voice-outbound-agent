# app/webhook_receiver/dependencies.py
import logging

from fastapi import Header, HTTPException, Request
from livekit.api.webhook import WebhookEvent

from app.core.settings import settings
from app.webhook_receiver.signature_verifier import make_webhook_receiver, verify_livekit_webhook

logger = logging.getLogger(__name__)

_receiver = make_webhook_receiver(
    api_key=settings.LIVEKIT_API_KEY,
    api_secret=settings.LIVEKIT_API_SECRET,
)


async def verified_livekit_event(
    request: Request,
    authorization: str = Header(...),
) -> WebhookEvent:
    raw_body = await request.body()
    return verify_livekit_webhook(raw_body, authorization, _receiver)
