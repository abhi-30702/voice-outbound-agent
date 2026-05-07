"""Unit tests for phone utilities."""
import pytest
from app.dialing_worker.phone_utils import is_e164, normalize_to_e164, PhoneValidationError


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

    def test_valid_short_number(self):
        """Valid short number (4 digits: + plus country code 1, plus 3 more digits)."""
        assert is_e164("+1123") is True

    def test_invalid_too_long(self):
        """Too many digits (>15)."""
        assert is_e164("+1" + "1" * 20) is False

    def test_invalid_letters(self):
        """Contains letters."""
        assert is_e164("+1123456789A") is False

    def test_empty_string(self):
        """Empty string."""
        assert is_e164("") is False


class TestNormalizeToE164:
    """Test phone number normalization to E.164."""

    def test_already_e164(self):
        """Already in E.164 format."""
        assert normalize_to_e164("+11234567890") == "+11234567890"

    def test_us_10_digit(self):
        """10-digit US number."""
        assert normalize_to_e164("1234567890") == "+11234567890"

    def test_us_formatted(self):
        """Formatted US number."""
        assert normalize_to_e164("(123) 456-7890") == "+11234567890"

    def test_us_with_dashes(self):
        """US number with dashes."""
        assert normalize_to_e164("123-456-7890") == "+11234567890"

    def test_india_with_country_code(self):
        """India number with country code prefix."""
        assert normalize_to_e164("919876543210", country_code="IN") == "+919876543210"

    def test_india_without_country_code(self):
        """India 10-digit number without country code."""
        assert normalize_to_e164("9876543210", country_code="IN") == "+919876543210"

    def test_uk_formatted(self):
        """UK formatted number."""
        result = normalize_to_e164("(0) 207 183 8750", country_code="UK")
        assert result == "+442071838750"

    def test_invalid_normalization_raises(self):
        """Cannot normalize invalid number."""
        with pytest.raises(PhoneValidationError):
            normalize_to_e164("abc123")

    def test_normalization_with_spaces(self):
        """Number with extra spaces."""
        assert normalize_to_e164("  123 456 7890  ") == "+11234567890"
