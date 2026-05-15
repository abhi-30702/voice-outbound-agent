import logging

from fastapi import HTTPException
from livekit.api import WebhookReceiver
from livekit.api.access_token import TokenVerifier
from livekit.api.webhook import WebhookEvent

logger = logging.getLogger(__name__)


def make_webhook_receiver(api_key: str, api_secret: str) -> WebhookReceiver:
    """Build a LiveKit WebhookReceiver for JWT signature verification."""
    verifier = TokenVerifier(api_key=api_key, api_secret=api_secret)
    return WebhookReceiver(verifier)


def verify_livekit_webhook(
    raw_body: bytes,
    auth_header: str,
    receiver: WebhookReceiver,
) -> WebhookEvent:
    """Parse and verify a LiveKit webhook request.

    Raises:
        HTTPException 403 if the JWT signature is invalid or missing.
    """
    try:
        return receiver.receive(raw_body.decode("utf-8"), auth_header)
    except Exception as exc:
        logger.warning("LiveKit webhook verification failed: %s", exc)
        raise HTTPException(status_code=403, detail="Invalid webhook signature") from exc
