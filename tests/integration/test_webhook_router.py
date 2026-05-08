# tests/integration/test_webhook_router.py
import hmac
import hashlib
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from app.webhook_receiver.main import app
from app.webhook_receiver.dependencies import verified_webhook_body

TEST_SECRET = "integration-test-secret"


def _make_sig(body: bytes, secret: str = TEST_SECRET) -> str:
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()


def _payload(event: str, call_id: str = "call_test_001") -> bytes:
    return json.dumps({"event": event, "call_id": call_id}).encode()


@pytest_asyncio.fixture
async def mock_redis():
    r = AsyncMock()
    r.exists = AsyncMock(return_value=0)
    r.setex = AsyncMock()
    r.aclose = AsyncMock()
    return r


@pytest_asyncio.fixture
async def mock_session_factory():
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=cm)
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    session.flush = AsyncMock()
    session.add = MagicMock()

    factory = MagicMock(return_value=cm)
    return factory


@pytest_asyncio.fixture
async def client(mock_redis, mock_session_factory):
    # ASGITransport does not trigger the ASGI lifespan — set app.state directly.
    app.state.redis = mock_redis
    app.state.session_factory = mock_session_factory
    with patch("app.core.settings.settings.RETELL_WEBHOOK_SECRET", TEST_SECRET):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c
    # Reset app state after each test to avoid bleed between tests.
    app.state._state.clear()


@pytest.mark.asyncio
async def test_valid_call_started_returns_200(client):
    body = _payload("call_started")
    # Mock dispatch so real handlers/services don't run (covered by unit tests)
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()):
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_invalid_signature_returns_403(client):
    body = _payload("call_started")
    response = await client.post(
        "/webhook",
        content=body,
        headers={"x-retell-signature": "bad-signature", "content-type": "application/json"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_missing_signature_header_returns_422(client):
    body = _payload("call_started")
    response = await client.post(
        "/webhook",
        content=body,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_event_returns_200_without_dispatch(client, mock_redis):
    mock_redis.exists = AsyncMock(return_value=1)  # Already seen
    body = _payload("call_started", "call_dup_001")

    with patch("app.webhook_receiver.router.dispatch", AsyncMock()) as mock_dispatch:
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
        mock_dispatch.assert_not_called()

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_unknown_event_type_returns_200(client):
    body = _payload("call_new_retell_event_2027")
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()):
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_call_ended_event_routes_to_dispatch(client):
    body = json.dumps({
        "event": "call_ended",
        "call_id": "call_test_002",
        "duration_ms": 45000,
        "disconnect_reason": "user_hangup",
    }).encode()
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()) as mock_dispatch:
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    assert response.status_code == 200
    call_args = mock_dispatch.call_args[0]
    assert call_args[0].event == "call_ended"


@pytest.mark.asyncio
async def test_call_analyzed_event_routes_to_dispatch(client):
    body = json.dumps({
        "event": "call_analyzed",
        "call_id": "call_test_003",
        "transcript": "Agent: Hello\nUser: Hi",
    }).encode()
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()) as mock_dispatch:
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    assert response.status_code == 200
    assert mock_dispatch.call_args[0][0].event == "call_analyzed"


@pytest.mark.asyncio
async def test_transcript_updated_returns_200(client):
    body = _payload("transcript_updated")
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()):
        response = await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_replay_key_set_on_new_event(client, mock_redis):
    body = _payload("call_started", "call_new_001")
    with patch("app.webhook_receiver.router.dispatch", AsyncMock()):
        await client.post(
            "/webhook",
            content=body,
            headers={"x-retell-signature": _make_sig(body), "content-type": "application/json"},
        )
    mock_redis.setex.assert_called_once_with(
        "webhook:seen:call_new_001:call_started", 600, "1"
    )
