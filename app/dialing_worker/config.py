# app/dialing_worker/config.py
from dataclasses import dataclass


@dataclass
class DialerConfig:
    """Configuration for dialing worker."""

    # Business hours (24-hour format)
    DEFAULT_START_HOUR: int = 8      # 8am
    DEFAULT_END_HOUR: int = 21       # 9pm

    # Rate limiting
    CALLS_PER_SECOND: float = 1.0    # Strict 1 CPS

    # Poll interval
    POLL_INTERVAL_SECONDS: int = 5   # Check for new leads every 5 seconds

    # Batch size
    BATCH_SIZE: int = 50             # Max leads per batch

    # Retry strategy
    MAX_RETRIES: int = 5             # Maximum retry attempts per lead
    INITIAL_BACKOFF_SECONDS: int = 2 # Starting backoff (exponential: 2, 4, 8, 16, 32)
