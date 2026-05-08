# app/dialing_worker/config.py
from dataclasses import dataclass


@dataclass
class DialerConfig:
    """Configuration for dialing worker.

    Attributes:
        retell_api_key: Retell AI API key
        retell_base_url: Retell API base URL
        retell_timeout_sec: HTTP request timeout in seconds
        batch_size: Max leads per dial batch
        poll_interval_sec: Seconds between polling for new leads
        start_hour: Start of calling hours (0-23), default 8am
        end_hour: End of calling hours (0-23), default 9pm
        max_retries: Maximum retry attempts per lead
    """

    retell_api_key: str
    retell_base_url: str = "https://api.retellai.com"
    retell_timeout_sec: float = 30.0
    batch_size: int = 50
    poll_interval_sec: int = 5
    start_hour: int = 8
    end_hour: int = 21
    max_retries: int = 5
