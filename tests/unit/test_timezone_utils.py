"""Unit tests for timezone utilities."""
from datetime import datetime
from unittest.mock import patch

import pytest
import pytz

from app.dialing_worker.timezone_utils import (
    get_local_time,
    is_within_calling_hours,
)


class TestGetLocalTime:
    """Tests for get_local_time function."""

    def test_get_local_time_valid_timezone(self):
        """Test getting local time for a valid timezone."""
        result = get_local_time("Asia/Kolkata")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_get_local_time_us_timezone(self):
        """Test getting local time for US timezone."""
        result = get_local_time("America/New_York")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_get_local_time_utc(self):
        """Test getting local time for UTC."""
        result = get_local_time("UTC")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_get_local_time_invalid_timezone(self):
        """Test that invalid timezone raises UnknownTimeZoneError."""
        with pytest.raises(pytz.exceptions.UnknownTimeZoneError):
            get_local_time("Invalid/Timezone")

    def test_get_local_time_aware_datetime(self):
        """Test that returned datetime is timezone-aware."""
        result = get_local_time("Europe/London")
        assert result.tzinfo is not None
        assert isinstance(result.tzinfo, pytz.tzinfo.BaseTzInfo)


class TestIsWithinCallingHours:
    """Tests for is_within_calling_hours function."""

    @patch("app.dialing_worker.timezone_utils.datetime")
    def test_within_calling_hours_8am(self, mock_datetime):
        """Test that 8am is within calling hours."""
        # Mock datetime.now() to return 8:00 AM in Asia/Kolkata
        tz = pytz.timezone("Asia/Kolkata")
        mock_time = tz.localize(datetime(2026, 5, 7, 8, 0, 0))
        mock_datetime.now.return_value = mock_time

        result = is_within_calling_hours("Asia/Kolkata")
        assert result is True

    @patch("app.dialing_worker.timezone_utils.datetime")
    def test_within_calling_hours_noon(self, mock_datetime):
        """Test that noon is within calling hours."""
        tz = pytz.timezone("America/New_York")
        mock_time = tz.localize(datetime(2026, 5, 7, 12, 0, 0))
        mock_datetime.now.return_value = mock_time

        result = is_within_calling_hours("America/New_York")
        assert result is True

    @patch("app.dialing_worker.timezone_utils.datetime")
    def test_within_calling_hours_8_59pm(self, mock_datetime):
        """Test that 8:59pm (20:59) is within calling hours."""
        tz = pytz.timezone("Europe/London")
        mock_time = tz.localize(datetime(2026, 5, 7, 20, 59, 0))
        mock_datetime.now.return_value = mock_time

        result = is_within_calling_hours("Europe/London")
        assert result is True

    @patch("app.dialing_worker.timezone_utils.datetime")
    def test_outside_calling_hours_before_8am(self, mock_datetime):
        """Test that 7:59am is outside calling hours."""
        tz = pytz.timezone("Asia/Kolkata")
        mock_time = tz.localize(datetime(2026, 5, 7, 7, 59, 0))
        mock_datetime.now.return_value = mock_time

        result = is_within_calling_hours("Asia/Kolkata")
        assert result is False

    @patch("app.dialing_worker.timezone_utils.datetime")
    def test_outside_calling_hours_after_9pm(self, mock_datetime):
        """Test that 9pm (21:00) is outside calling hours."""
        tz = pytz.timezone("America/New_York")
        mock_time = tz.localize(datetime(2026, 5, 7, 21, 0, 0))
        mock_datetime.now.return_value = mock_time

        result = is_within_calling_hours("America/New_York")
        assert result is False

    @patch("app.dialing_worker.timezone_utils.datetime")
    def test_outside_calling_hours_midnight(self, mock_datetime):
        """Test that midnight is outside calling hours."""
        tz = pytz.timezone("Europe/London")
        mock_time = tz.localize(datetime(2026, 5, 7, 0, 0, 0))
        mock_datetime.now.return_value = mock_time

        result = is_within_calling_hours("Europe/London")
        assert result is False

    def test_custom_calling_hours(self):
        """Test with custom calling hours (9am-5pm)."""
        with patch("app.dialing_worker.timezone_utils.datetime") as mock_datetime:
            tz = pytz.timezone("America/Los_Angeles")
            # 9:00 AM
            mock_time = tz.localize(datetime(2026, 5, 7, 9, 0, 0))
            mock_datetime.now.return_value = mock_time

            result = is_within_calling_hours(
                "America/Los_Angeles", start_hour=9, end_hour=17
            )
            assert result is True

    def test_custom_calling_hours_outside(self):
        """Test custom hours with time outside range."""
        with patch("app.dialing_worker.timezone_utils.datetime") as mock_datetime:
            tz = pytz.timezone("America/Los_Angeles")
            # 8:00 AM (before 9am start)
            mock_time = tz.localize(datetime(2026, 5, 7, 8, 0, 0))
            mock_datetime.now.return_value = mock_time

            result = is_within_calling_hours(
                "America/Los_Angeles", start_hour=9, end_hour=17
            )
            assert result is False

    def test_invalid_start_hour(self):
        """Test that invalid start_hour raises ValueError."""
        with pytest.raises(ValueError, match="start_hour must be 0-23"):
            is_within_calling_hours("Asia/Kolkata", start_hour=24)

    def test_invalid_start_hour_negative(self):
        """Test that negative start_hour raises ValueError."""
        with pytest.raises(ValueError, match="start_hour must be 0-23"):
            is_within_calling_hours("Asia/Kolkata", start_hour=-1)

    def test_invalid_end_hour(self):
        """Test that invalid end_hour raises ValueError."""
        with pytest.raises(ValueError, match="end_hour must be 0-23"):
            is_within_calling_hours("Asia/Kolkata", end_hour=25)

    def test_invalid_end_hour_negative(self):
        """Test that negative end_hour raises ValueError."""
        with pytest.raises(ValueError, match="end_hour must be 0-23"):
            is_within_calling_hours("Asia/Kolkata", end_hour=-1)

    def test_invalid_timezone_in_is_within_calling_hours(self):
        """Test that invalid timezone raises UnknownTimeZoneError."""
        with pytest.raises(pytz.exceptions.UnknownTimeZoneError):
            is_within_calling_hours("Invalid/TZ")

    @patch("app.dialing_worker.timezone_utils.datetime")
    def test_boundary_start_hour(self, mock_datetime):
        """Test boundary condition at exactly start_hour."""
        tz = pytz.timezone("Asia/Kolkata")
        mock_time = tz.localize(datetime(2026, 5, 7, 8, 0, 0))
        mock_datetime.now.return_value = mock_time

        result = is_within_calling_hours("Asia/Kolkata", start_hour=8, end_hour=21)
        assert result is True

    @patch("app.dialing_worker.timezone_utils.datetime")
    def test_boundary_end_hour_exclusive(self, mock_datetime):
        """Test boundary condition at exactly end_hour (should be exclusive)."""
        tz = pytz.timezone("Asia/Kolkata")
        mock_time = tz.localize(datetime(2026, 5, 7, 21, 0, 0))
        mock_datetime.now.return_value = mock_time

        result = is_within_calling_hours("Asia/Kolkata", start_hour=8, end_hour=21)
        assert result is False
