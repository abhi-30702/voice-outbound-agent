import hmac
import hashlib


def verify_retell_signature(
    raw_body: bytes,
    signature_header: str,
    webhook_secret: str,
) -> bool:
    expected = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
