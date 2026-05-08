import pytest
from app.post_call_analysis.dnc_keywords import DNC_PHRASES, scan


def test_do_not_call_triggers_scan():
    assert scan("Please do not call me again") is True


def test_remove_me_triggers_scan():
    assert scan("Just remove me from your list please") is True


def test_case_insensitive_matching():
    assert scan("DO NOT CALL me ever") is True


def test_neutral_transcript_does_not_trigger():
    assert scan("I might be interested, call me back tomorrow") is False


def test_all_phrases_trigger():
    for phrase in DNC_PHRASES:
        assert scan(f"The caller said: {phrase}") is True, f"Phrase not matched: {phrase!r}"
