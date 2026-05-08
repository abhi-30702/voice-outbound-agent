"""Timezone utilities for the dialing worker."""
from datetime import datetime

import pytz


def get_local_time(timezone: str) -> datetime:
    """Get current local time in the specified timezone.

    Args:
        timezone: IANA timezone string (e.g., "Asia/Kolkata", "America/New_York")

    Returns:
        Current datetime in the specified timezone (aware, with tzinfo)

    Raises:
        pytz.exceptions.UnknownTimeZoneError: If timezone is invalid
    """
    tz = pytz.timezone(timezone)
    return datetime.now(tz)


def is_within_calling_hours(
    timezone: str,
    start_hour: int = 8,
    end_hour: int = 21,
) -> bool:
    """Check if current time is within calling hours for the given timezone.

    Args:
        timezone: IANA timezone string (e.g., "Asia/Kolkata", "America/New_York")
        start_hour: Start hour (0-23), default 8 (8am)
        end_hour: End hour (0-23), default 21 (9pm)

    Returns:
        True if current hour is >= start_hour and < end_hour, False otherwise

    Raises:
        pytz.exceptions.UnknownTimeZoneError: If timezone is invalid
        ValueError: If start_hour or end_hour are invalid (not 0-23)
    """
    if not (0 <= start_hour <= 23):
        raise ValueError(f"start_hour must be 0-23, got {start_hour}")
    if not (0 <= end_hour <= 23):
        raise ValueError(f"end_hour must be 0-23, got {end_hour}")

    local_time = get_local_time(timezone)
    current_hour = local_time.hour

    # Simple range check: start_hour <= current_hour < end_hour
    # This handles the common case where start < end
    return start_hour <= current_hour < end_hour
