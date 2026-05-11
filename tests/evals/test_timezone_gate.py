"""Timezone gate eval: 5 timezones frozen at 2026-01-15 14:00 UTC.

Expected results at that moment:
  America/New_York  → 09:00 EST  → IN  hours ✓
  Europe/London     → 14:00 GMT  → IN  hours ✓
  Asia/Kolkata      → 19:30 IST  → IN  hours ✓
  Australia/Sydney  → 01:00 AEDT → OUT of hours ✗
  Pacific/Auckland  → 03:00 NZDT → OUT of hours ✗

No database required.
Run: pytest tests/evals/test_timezone_gate.py -v
"""
import pytest
from freezegun import freeze_time

from app.dialing_worker.timezone_utils import is_within_calling_hours

FROZEN = "2026-01-15 14:00:00"


@freeze_time(FROZEN)
class TestTimezoneGate:

    def test_new_york_in_hours(self):
        assert is_within_calling_hours("America/New_York") is True

    def test_london_in_hours(self):
        assert is_within_calling_hours("Europe/London") is True

    def test_kolkata_in_hours(self):
        assert is_within_calling_hours("Asia/Kolkata") is True

    def test_sydney_out_of_hours(self):
        assert is_within_calling_hours("Australia/Sydney") is False

    def test_auckland_out_of_hours(self):
        assert is_within_calling_hours("Pacific/Auckland") is False
