# tests/evals/test_signature_verification.py
"""
Eval: HTTP-layer HMAC signature verification tests.

Verifies that the /webhook endpoint correctly enforces Retell signature validation:
- Valid HMAC → 200 OK
- Tampered body (HMAC was for original) → 403 Forbidden
- Missing x-retell-signature header → 422 Unprocessable Entity
"""

import hmac
import hashlib
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from app.webhook_receiver.main import app

TEST_SECRET = "test-secret"


def _make_sig(body: bytes, secret: str = TEST_SECRET) -> str:
    """Compute HMAC-SHA256 signature for a body."""
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()


@pytest_asyncio.fixture
async def mock_redis():
    """Mock Redis with async context manager and idempotent methods."""
    r = AsyncMock()
    r.exists = AsyncMock(return_value=0)
    r.setex = AsyncMock()
    r.aclose = AsyncMock()
    return r


@pytest_asyncio.fixture
async def mock_session_factory():
    """Mock SQLAlchemy session factory for database mocking."""
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=cm)
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    session.flush = AsyncMock()
    session.add = MagicMock()

    factory = MagicMock(return_value=cm)
    return factory


@pytest_asyncio.fixture
async def client(mock_redis, mock_session_factory):
    """
    HTTP client against the webhook app with mocked Redis and DB.

    ASGITransport does not trigger ASGI lifespan, so we inject dependencies
    directly into app.state. Clean up after each test to avoid state bleed.
    """
    app.state.redis = mock_redis
    app.state.session_factory = mock_session_factory
    with patch("app.core.settings.settings.RETELL_WEBHOOK_SECRET", TEST_SECRET):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c
    app.state._state.clear()


@pytest.mark.asyncio
async def test_valid_sig_returns_200(client):
    """
    Valid HMAC signature should return 200 OK.

    Setup: compute HMAC from the correct body using TEST_SECRET.
    POST with body + signature + content-type header.
    Patch dispatch to prevent real handler execution.
    """
    body = json.dumps(
        {"event": "call_started", "call_id": "call_sig_001"}
    ).encode()
    sig = _make_sig(body)

    with patch("app.webhook_receiver.router.dispatch", AsyncMock()):
        response = await client.post(
            "/webhook",
            content=body,
            headers={
                "x-retell-signature": sig,
                "content-type": "application/json",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_tampered_body_returns_403(client):
    """
    Body tampered after signature was computed should return 403 Forbidden.

    Setup: compute HMAC from original body.
    Flip one byte of the body.
    POST with tampered body but original HMAC.
    Signature verification should fail → 403.
    """
    body = json.dumps(
        {"event": "call_started", "call_id": "call_sig_001"}
    ).encode()
    sig = _make_sig(body)  # Signature for original body

    # Tamper: flip first byte
    tampered = bytearray(body)
    tampered[0] ^= 0xFF
    tampered = bytes(tampered)

    response = await client.post(
        "/webhook",
        content=tampered,
        headers={
            "x-retell-signature": sig,
            "content-type": "application/json",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_missing_sig_header_returns_422(client):
    """
    Missing x-retell-signature header should return 422 Unprocessable Entity.

    FastAPI returns 422 when a required Header() is absent.
    POST with body but NO x-retell-signature header.
    """
    body = json.dumps(
        {"event": "call_started", "call_id": "call_sig_001"}
    ).encode()

    response = await client.post(
        "/webhook",
        content=body,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
