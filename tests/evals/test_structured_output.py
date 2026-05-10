"""Structured output evals — no database required, all Anthropic API calls are mocked."""
import pytest
from unittest.mock import patch, MagicMock

from app.post_call_analysis.worker import _call_claude
from app.post_call_analysis.schemas import ExtractionResult


@pytest.mark.parametrize(
    "transcript,expected_outcome,expected_dnc,expected_sentiment",
    [
        pytest.param(
            "I'm very interested in your product, let's move forward",
            "interested",
            False,
            "positive",
            id="qualified",
        ),
        pytest.param(
            "Not interested at all, please don't call again",
            "not_interested",
            False,
            "neutral",
            id="unqualified",
        ),
        pytest.param(
            "Remove me from your list immediately, I do not want to be called",
            "dnc_request",
            True,
            "negative",
            id="dnc_request",
        ),
    ],
)
def test_structured_output_schema(transcript, expected_outcome, expected_dnc, expected_sentiment):
    """Verify _call_claude returns valid ExtractionResult with expected fields and sentiment."""
    extraction_dict = {
        "call_outcome": expected_outcome,
        "callback_time": None,
        "objections_raised": [],
        "next_action": "follow up next week",
        "summary": "Call summary from transcript",
        "sentiment_reason": "Caller tone indicated sentiment",
        "lead_temperature": "warm",
        "sentiment": expected_sentiment,
        "dnc_requested": expected_dnc,
    }

    with patch("app.post_call_analysis.worker.anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.input = extraction_dict
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        result = _call_claude(transcript)

        assert isinstance(result, ExtractionResult)
        assert ExtractionResult.model_validate(result.model_dump()) == result
        assert result.call_outcome == expected_outcome
        assert result.dnc_requested == expected_dnc
        assert result.sentiment == expected_sentiment
