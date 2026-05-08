"""Custom exceptions for the dialing worker module."""


class DialingWorkerError(Exception):
    """Base exception for all dialing worker errors."""

    pass


class PhoneValidationError(DialingWorkerError):
    """Raised when phone number validation fails."""

    pass


class RetellAPIError(DialingWorkerError):
    """Raised when Retell API request fails.

    Attributes:
        message: Error message
        retriable: Whether the error is retriable (e.g., 429, 5xx, timeout)
        status_code: HTTP status code, if applicable (None for timeout/network errors)
    """

    def __init__(
        self,
        message: str,
        retriable: bool = False,
        status_code: int | None = None,
    ):
        """Initialize RetellAPIError.

        Args:
            message: Detailed error message
            retriable: Whether this error can be retried
            status_code: HTTP status code if applicable
        """
        super().__init__(message)
        self.message = message
        self.retriable = retriable
        self.status_code = status_code

    def __repr__(self) -> str:
        return (
            f"RetellAPIError(message={self.message!r}, "
            f"retriable={self.retriable}, status_code={self.status_code})"
        )
