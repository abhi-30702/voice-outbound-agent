"""Evals for structured output schema from post-call analysis Claude integration.

Tests validate that _call_claude returns ExtractionResult with correct schema
and that Claude's tool_use blocks are properly parsed into the result.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.post_call_analysis.worker import _call_claude
from app.post_call_analysis.schemas import ExtractionResult


@pytest.mark.parametrize(
    "transcript,expected_outcome,expected_dnc",
    [
        pytest.param(
            "I'm very interested in your product, let's move forward",
            "interested",
            False,
            id="qualified",
        ),
        pytest.param(
            "Not interested at all, please don't call again",
            "not_interested",
            False,
            id="unqualified",
        ),
        pytest.param(
            "Remove me from your list immediately, I do not want to be called",
            "dnc_request",
            True,
            id="dnc_request",
        ),
    ],
)
def test_structured_output_schema(transcript, expected_outcome, expected_dnc):
    """Test that _call_claude returns valid ExtractionResult with expected fields.

    Mocks the Anthropic API to return a tool_use block containing
    a complete ExtractionResult dict. Verifies that:
    1. The result passes Pydantic validation
    2. call_outcome matches expected
    3. dnc_requested matches expected
    """
    # Build the extraction dict that Claude would return in tool_use.input
    extraction_dict = {
        "call_outcome": expected_outcome,
        "callback_time": None,
        "objections_raised": [],
        "next_action": "follow up next week",
        "summary": "Call summary from transcript",
        "sentiment_reason": "Caller tone indicated sentiment",
        "lead_temperature": "warm",
        "sentiment": "positive" if expected_outcome == "interested" else "neutral",
        "dnc_requested": expected_dnc,
    }

    # Mock the Anthropic client
    with patch("app.post_call_analysis.worker.anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # Build mock response with tool_use block
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.input = extraction_dict
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        # Call the function
        result = _call_claude(transcript)

        # Assertions
        assert isinstance(result, ExtractionResult)
        # Validate that result can round-trip through Pydantic
        assert ExtractionResult.model_validate(result.model_dump()) is not None
        assert result.call_outcome == expected_outcome
        assert result.dnc_requested == expected_dnc
