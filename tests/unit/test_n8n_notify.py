import pytest
import httpx
import respx
from httpx import Response
from unittest.mock import patch

from app.post_call_analysis.worker import _notify_n8n

WEBHOOK_URL = "http://n8n:5678/webhook/post-call"

SAMPLE_PAYLOAD = {
    "call_id": "00000000-0000-0000-0000-000000000001",
    "lead_id": "00000000-0000-0000-0000-000000000002",
    "phone_number": "+919876543210",
    "first_name": "Ravi",
    "last_name": "Sharma",
    "company": "ABC Corp",
    "call_outcome": "callback_requested",
    "callback_requested": True,
    "callback_time": "2026-05-10T10:00:00+05:30",
    "summary": "Lead asked for callback.",
    "lead_temperature": "hot",
    "sentiment": "positive",
    "objections_raised": ["too busy"],
    "next_action": "Schedule callback.",
}


@pytest.mark.asyncio
async def test_notify_sends_correct_url_and_secret():
    with respx.mock() as m:
        route = m.post(WEBHOOK_URL).mock(return_value=Response(200))
        with patch("app.post_call_analysis.worker.settings") as s:
            s.N8N_WEBHOOK_URL = WEBHOOK_URL
            s.N8N_WEBHOOK_SECRET = "test-secret"
            await _notify_n8n(SAMPLE_PAYLOAD)
    assert route.called
    assert route.calls[0].request.headers["X-Internal-Webhook-Secret"] == "test-secret"


@pytest.mark.asyncio
async def test_notify_skips_when_url_empty():
    with respx.mock() as m:
        # no routes registered — any HTTP call would raise
        with patch("app.post_call_analysis.worker.settings") as s:
            s.N8N_WEBHOOK_URL = ""
            s.N8N_WEBHOOK_SECRET = ""
            await _notify_n8n(SAMPLE_PAYLOAD)  # must not raise, must not call HTTP
    assert not m.calls


@pytest.mark.asyncio
async def test_notify_swallows_connect_error():
    with respx.mock() as m:
        m.post(WEBHOOK_URL).mock(side_effect=httpx.ConnectError("refused"))
        with patch("app.post_call_analysis.worker.settings") as s:
            s.N8N_WEBHOOK_URL = WEBHOOK_URL
            s.N8N_WEBHOOK_SECRET = "secret"
            await _notify_n8n(SAMPLE_PAYLOAD)  # must not raise


@pytest.mark.asyncio
async def test_notify_swallows_read_timeout():
    with respx.mock() as m:
        m.post(WEBHOOK_URL).mock(side_effect=httpx.ReadTimeout("timed out"))
        with patch("app.post_call_analysis.worker.settings") as s:
            s.N8N_WEBHOOK_URL = WEBHOOK_URL
            s.N8N_WEBHOOK_SECRET = "secret"
            await _notify_n8n(SAMPLE_PAYLOAD)  # must not raise


@pytest.mark.asyncio
async def test_notify_swallows_http_500():
    with respx.mock() as m:
        route = m.post(WEBHOOK_URL).mock(return_value=Response(500))
        with patch("app.post_call_analysis.worker.settings") as s:
            s.N8N_WEBHOOK_URL = WEBHOOK_URL
            s.N8N_WEBHOOK_SECRET = "secret"
            await _notify_n8n(SAMPLE_PAYLOAD)  # 500 is not an exception; must not raise
    assert route.called
