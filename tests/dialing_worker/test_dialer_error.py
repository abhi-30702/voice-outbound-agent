from app.dialing_worker.errors import DialerError


def test_dialer_error_retriable():
    e = DialerError(message="rate limit", retriable=True, status_code=429)
    assert e.retriable is True
    assert e.status_code == 429
    assert "rate limit" in str(e)


def test_dialer_error_permanent():
    e = DialerError(message="bad request", retriable=False, status_code=400)
    assert e.retriable is False
