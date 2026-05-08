"""Phone number utilities for the dialing worker."""
import re


class PhoneValidationError(Exception):
    """Raised when phone number validation or normalization fails."""

    pass


def is_e164(phone_number: str) -> bool:
    """
    Check if phone number is valid E.164 format.

    Valid: +1234567890, +919876543210
    Invalid: 123-456-7890, (123) 456-7890, 9876543210 (no +)

    E.164 format:
    - Must start with +
    - First digit must be 1-9 (not 0)
    - Must have 1-14 more digits (total 2-15 digits including the country code)

    Args:
        phone_number: String to validate

    Returns:
        True if valid E.164, False otherwise
    """
    pattern = r"^\+[1-9]\d{1,14}$"
    return bool(re.match(pattern, phone_number))


def normalize_to_e164(phone_number: str, country_code: str = "US") -> str:
    """
    Normalize common phone formats to E.164.

    Handles:
    - 10-digit US: 1234567890 → +11234567890
    - Formatted: (123) 456-7890 → +11234567890
    - With country code: 91 9876543210 → +919876543210
    - Already E.164: +1234567890 → +1234567890

    Args:
        phone_number: Raw phone number string
        country_code: ISO country code (e.g., "US", "IN", "UK")

    Returns:
        E.164 formatted number

    Raises:
        PhoneValidationError: If number cannot be normalized
    """
    # Remove common formatting characters and strip whitespace
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", phone_number.strip())

    # If already E.164, return as-is
    if is_e164(cleaned):
        return cleaned

    # Map ISO country codes to country calling codes
    country_codes = {"US": "1", "IN": "91", "UK": "44"}
    cc = country_codes.get(country_code, "1")

    # Special handling for UK: remove leading 0 from national numbers
    if country_code == "UK" and cleaned.startswith("0"):
        cleaned = cleaned[1:]

    # Determine if the number already has the country code prefix
    # Use country-specific logic based on expected lengths
    has_country_code = False

    if country_code == "US":
        # US: 10-digit = national, 11-digit starting with 1 = international
        if len(cleaned) == 11 and cleaned.startswith("1"):
            has_country_code = True
    elif country_code == "IN":
        # India: 10-digit = national, 12-digit starting with 91 = international
        if len(cleaned) == 12 and cleaned.startswith("91"):
            has_country_code = True
    elif country_code == "UK":
        # UK: After removing leading 0, should be 10 digits with country code or 9 digits national
        if len(cleaned) == 10 and cleaned.startswith("44"):
            has_country_code = True
    else:
        # For unknown countries, only consider it has country code if it starts with cc
        # and the total length makes sense (more than just the country code)
        if len(cc) > 1 and cleaned.startswith(cc) and len(cleaned) > len(cc):
            has_country_code = True

    if has_country_code:
        # Already has country code, just add +
        candidate = "+" + cleaned
    else:
        # Add country code
        candidate = "+" + cc + cleaned

    if is_e164(candidate):
        return candidate

    raise PhoneValidationError(f"Cannot normalize {phone_number} to E.164")
