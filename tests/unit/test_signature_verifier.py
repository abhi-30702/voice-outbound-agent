import hmac
import hashlib
import pytest
from app.webhook_receiver.signature_verifier import verify_retell_signature


def _make_sig(body: bytes, secret: str) -> str:
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()


def test_valid_signature_passes():
    body = b'{"event":"call_started","call_id":"abc"}'
    secret = "test-secret"
    assert verify_retell_signature(body, _make_sig(body, secret), secret) is True


def test_tampered_body_fails():
    body = b'{"event":"call_started","call_id":"abc"}'
    tampered = b'{"event":"call_started","call_id":"hacked"}'
    secret = "test-secret"
    sig = _make_sig(body, secret)
    assert verify_retell_signature(tampered, sig, secret) is False


def test_wrong_secret_fails():
    body = b'{"event":"call_started","call_id":"abc"}'
    sig = _make_sig(body, "correct")
    assert verify_retell_signature(body, sig, "wrong") is False


def test_empty_body_valid_sig():
    body = b""
    secret = "s"
    assert verify_retell_signature(body, _make_sig(body, secret), secret) is True


def test_returns_bool_not_string():
    body = b'{"test":true}'
    secret = "secret"
    result = verify_retell_signature(body, _make_sig(body, secret), secret)
    assert isinstance(result, bool)
