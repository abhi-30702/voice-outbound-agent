import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from app.webhook_receiver.main import app
    return app


def test_livekit_webhook_endpoint_exists(app):
    client = TestClient(app, raise_server_exceptions=False)
    # Without valid JWT this returns 422 (missing Authorization header) or 403,
    # but NOT 404 — which proves the route is registered.
    resp = client.post("/webhook/livekit", content=b"{}")
    assert resp.status_code != 404


def test_old_retell_webhook_gone(app):
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/webhook", content=b"{}")
    assert resp.status_code == 404
