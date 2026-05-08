# app/webhook_receiver/config.py

FAILED_DISCONNECT_REASONS: frozenset[str] = frozenset({
    "error",
    "timeout",
    "dial_timeout",
    "dial_failed",
})

REPLAY_TTL_SECONDS: int = 600       # 10 minutes
TIMESTAMP_TOLERANCE_SECONDS: int = 300  # 5 minutes
