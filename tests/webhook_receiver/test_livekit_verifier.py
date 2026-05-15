import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from app.webhook_receiver.signature_verifier import verify_livekit_webhook


def test_valid_token_returns_event():
    mock_receiver = MagicMock()
    mock_event = MagicMock()
    mock_receiver.receive.return_value = mock_event

    result = verify_livekit_webhook(b'{"event":"room_started"}', "Bearer valid-token", mock_receiver)
    assert result is mock_event
    mock_receiver.receive.assert_called_once_with('{"event":"room_started"}', "Bearer valid-token")


def test_invalid_token_raises_http_403():
    mock_receiver = MagicMock()
    mock_receiver.receive.side_effect = Exception("invalid JWT signature")

    with pytest.raises(HTTPException) as exc_info:
        verify_livekit_webhook(b'{"event":"room_started"}', "Bearer bad-token", mock_receiver)
    assert exc_info.value.status_code == 403
