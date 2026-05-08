# app/webhook_receiver/dependencies.py
import logging

from fastapi import Header, HTTPException, Request

from app.core.settings import settings
from app.webhook_receiver.signature_verifier import verify_retell_signature

logger = logging.getLogger(__name__)


async def verified_webhook_body(
    request: Request,
    x_retell_signature: str = Header(...),
) -> bytes:
    raw_body = await request.body()

    if not verify_retell_signature(raw_body, x_retell_signature, settings.RETELL_WEBHOOK_SECRET):
        logger.warning(
            "Webhook signature verification failed",
            extra={"remote": request.client.host if request.client else "unknown"},
        )
        raise HTTPException(status_code=403, detail="Invalid signature")

    return raw_body
