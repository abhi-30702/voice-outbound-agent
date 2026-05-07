"""Phone number utilities for the dialing worker."""
import re


def is_e164(phone_number: str) -> bool:
    """
    Check if phone number is valid E.164 format.

    Valid: +1234567890, +919876543210
    Invalid: 123-456-7890, (123) 456-7890, 9876543210 (no +)

    E.164 format:
    - Must start with +
    - First digit must be 1-9 (not 0)
    - Must have 6-14 more digits (total 7-15 digits including the country code)

    Args:
        phone_number: String to validate

    Returns:
        True if valid E.164, False otherwise
    """
    pattern = r"^\+[1-9]\d{6,14}$"
    return bool(re.match(pattern, phone_number))
