class DialingWorkerError(Exception):
    """Base exception for all dialing worker errors."""
    pass


class PhoneValidationError(DialingWorkerError):
    """Raised when phone number validation fails."""
    pass


class DialerError(DialingWorkerError):
    """Raised when the telephony API call fails.

    Attributes:
        message: Error message
        retriable: True for transient errors (rate limit, 5xx, timeout)
        status_code: HTTP status code if applicable
    """

    def __init__(self, message: str, retriable: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.retriable = retriable
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"DialerError(message={self.message!r}, retriable={self.retriable}, status_code={self.status_code})"


# Backward-compatible alias — worker.py and retell_client.py still reference this
# name; they will be updated in Task 5.
RetellAPIError = DialerError
