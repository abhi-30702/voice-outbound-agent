# tests/unit/test_models.py
"""Unit tests for ORM models."""

import pytest
from uuid import UUID
from datetime import datetime
from sqlalchemy.inspection import inspect
from app.models import (
    Campaign, CampaignStatus,
    Contact, ContactStatus,
    Call, CallStatus,
    Transcript, SentimentLevel,
    DNCEntry, DNCSource,
)


class TestCampaignModel:
    """Tests for Campaign model."""

    def test_campaign_has_required_columns(self):
        """Campaign should have all required columns."""
        mapper = inspect(Campaign)
        columns = {c.name for c in mapper.columns}

        assert "id" in columns
        assert "name" in columns
        assert "status" in columns
        assert "prompt_template" in columns
        assert "llm_config" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

    def test_campaign_status_enum_values(self):
        """CampaignStatus enum should have expected values."""
        assert CampaignStatus.DRAFT.value == "draft"
        assert CampaignStatus.ACTIVE.value == "active"
        assert CampaignStatus.PAUSED.value == "paused"
        assert CampaignStatus.COMPLETED.value == "completed"


class TestContactModel:
    """Tests for Contact model."""

    def test_contact_has_required_columns(self):
        """Contact should have all required columns."""
        mapper = inspect(Contact)
        columns = {c.name for c in mapper.columns}

        assert "id" in columns
        assert "phone_number" in columns
        assert "timezone" in columns
        assert "campaign_id" in columns
        assert "status" in columns
        assert "retry_count" in columns
        assert "custom_vars" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

    def test_contact_status_enum_values(self):
        """ContactStatus enum should have expected values."""
        assert ContactStatus.PENDING.value == "pending"
        assert ContactStatus.CALLING.value == "calling"
        assert ContactStatus.COMPLETED.value == "completed"
        assert ContactStatus.FAILED.value == "failed"
        assert ContactStatus.FAILED_DNC.value == "failed_dnc"


class TestCallModel:
    """Tests for Call model."""

    def test_call_has_required_columns(self):
        """Call should have all required columns."""
        mapper = inspect(Call)
        columns = {c.name for c in mapper.columns}

        assert "id" in columns
        assert "lead_id" in columns
        assert "retell_call_id" in columns
        assert "status" in columns
        assert "start_time" in columns
        assert "duration_sec" in columns
        assert "recording_url" in columns
        assert "created_at" in columns

    def test_call_status_enum_values(self):
        """CallStatus enum should have expected values."""
        assert CallStatus.PENDING.value == "pending"
        assert CallStatus.CALLING.value == "calling"
        assert CallStatus.COMPLETED.value == "completed"
        assert CallStatus.FAILED.value == "failed"


class TestTranscriptModel:
    """Tests for Transcript model."""

    def test_transcript_has_required_columns(self):
        """Transcript should have all required columns."""
        mapper = inspect(Transcript)
        columns = {c.name for c in mapper.columns}

        assert "id" in columns
        assert "call_id" in columns
        assert "raw_transcript" in columns
        assert "structured_data" in columns
        assert "sentiment" in columns
        assert "created_at" in columns

    def test_sentiment_enum_values(self):
        """SentimentLevel enum should have expected values."""
        assert SentimentLevel.POSITIVE.value == "positive"
        assert SentimentLevel.NEUTRAL.value == "neutral"
        assert SentimentLevel.NEGATIVE.value == "negative"


class TestDNCEntryModel:
    """Tests for DNCEntry model."""

    def test_dnc_entry_has_required_columns(self):
        """DNCEntry should have all required columns."""
        mapper = inspect(DNCEntry)
        columns = {c.name for c in mapper.columns}

        assert "id" in columns
        assert "phone_number" in columns
        assert "source" in columns
        assert "added_at" in columns

    def test_dnc_source_enum_values(self):
        """DNCSource enum should have expected values."""
        assert DNCSource.MANUAL.value == "manual"
        assert DNCSource.NATIONAL_DNC.value == "national_dnc"
        assert DNCSource.CALLER_REQUEST.value == "caller_request"


class TestModelIndexes:
    """Tests for model indexes."""

    def test_contact_has_phone_index(self):
        """Contact should have an index on phone_number."""
        mapper = inspect(Contact)
        table = mapper.mapped_table
        index_names = {idx.name for idx in table.indexes}
        assert any("phone" in name for name in index_names)

    def test_dnc_entry_has_unique_phone_index(self):
        """DNCEntry should have unique index on phone_number."""
        mapper = inspect(DNCEntry)
        columns = {c.name for c in mapper.columns}
        phone_col = [c for c in mapper.columns if c.name == "phone_number"][0]
        assert phone_col.unique
