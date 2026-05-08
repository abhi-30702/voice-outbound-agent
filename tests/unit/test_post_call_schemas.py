# tests/unit/test_post_call_schemas.py
import pytest
from pydantic import ValidationError
from app.post_call_analysis.schemas import ExtractionResult


VALID_DATA = {
    "call_outcome": "interested",
    "callback_time": None,
    "objections_raised": ["price too high"],
    "next_action": "Schedule follow-up call",
    "summary": "Lead expressed interest but raised price concerns.",
    "sentiment_reason": "Positive tone throughout; expressed genuine interest.",
    "lead_temperature": "warm",
    "sentiment": "positive",
    "dnc_requested": False,
}


def test_valid_extraction_result_passes():
    result = ExtractionResult(**VALID_DATA)
    assert result.call_outcome == "interested"
    assert result.sentiment == "positive"
    assert result.dnc_requested is False


def test_callback_time_none_is_valid():
    result = ExtractionResult(**{**VALID_DATA, "callback_time": None})
    assert result.callback_time is None


def test_empty_objections_list_is_valid():
    result = ExtractionResult(**{**VALID_DATA, "objections_raised": []})
    assert result.objections_raised == []


def test_missing_required_field_raises():
    data = {k: v for k, v in VALID_DATA.items() if k != "call_outcome"}
    with pytest.raises(ValidationError):
        ExtractionResult(**data)


def test_invalid_call_outcome_raises():
    with pytest.raises(ValidationError):
        ExtractionResult(**{**VALID_DATA, "call_outcome": "maybe"})


def test_invalid_sentiment_raises():
    with pytest.raises(ValidationError):
        ExtractionResult(**{**VALID_DATA, "sentiment": "very_positive"})


def test_invalid_lead_temperature_raises():
    with pytest.raises(ValidationError):
        ExtractionResult(**{**VALID_DATA, "lead_temperature": "lukewarm"})


def test_model_dump_returns_dict():
    result = ExtractionResult(**VALID_DATA)
    dumped = result.model_dump()
    assert isinstance(dumped, dict)
    assert dumped["call_outcome"] == "interested"
    assert dumped["dnc_requested"] is False
