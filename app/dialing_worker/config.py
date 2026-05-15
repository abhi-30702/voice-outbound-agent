from dataclasses import dataclass


@dataclass
class DialerConfig:
    """Configuration for the LiveKit-based dialing worker.

    Attributes:
        livekit_url: LiveKit Cloud WSS URL (e.g. wss://project.livekit.cloud)
        livekit_api_key: LiveKit API key
        livekit_api_secret: LiveKit API secret
        livekit_sip_trunk_id: SIP trunk ID configured in LiveKit console
        batch_size: Max leads per dial batch
        poll_interval_sec: Seconds between DB polls for new leads
        start_hour: Start of calling hours (0-23), default 8am
        end_hour: End of calling hours (0-23), default 9pm
        max_retries: Maximum retry attempts per lead
    """

    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    livekit_sip_trunk_id: str
    batch_size: int = 50
    poll_interval_sec: int = 5
    start_hour: int = 8
    end_hour: int = 21
    max_retries: int = 5
