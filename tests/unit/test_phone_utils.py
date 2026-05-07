"""Unit tests for phone utilities."""
import pytest
from app.dialing_worker.phone_utils import is_e164


class TestIsE164:
    """Test E.164 phone validation."""

    def test_valid_us_number(self):
        """Valid US E.164 number."""
        assert is_e164("+11234567890") is True

    def test_valid_india_number(self):
        """Valid India E.164 number."""
        assert is_e164("+919876543210") is True

    def test_valid_uk_number(self):
        """Valid UK E.164 number."""
        assert is_e164("+442071838750") is True

    def test_invalid_no_plus(self):
        """No leading plus sign."""
        assert is_e164("11234567890") is False

    def test_invalid_plus_zero(self):
        """Plus followed by zero (invalid)."""
        assert is_e164("+01234567890") is False

    def test_invalid_formatted(self):
        """Formatted US number."""
        assert is_e164("(123) 456-7890") is False

    def test_invalid_too_short(self):
        """Too few digits."""
        assert is_e164("+1123") is False

    def test_invalid_too_long(self):
        """Too many digits (>15)."""
        assert is_e164("+1" + "1" * 20) is False

    def test_invalid_letters(self):
        """Contains letters."""
        assert is_e164("+1123456789A") is False

    def test_empty_string(self):
        """Empty string."""
        assert is_e164("") is False
