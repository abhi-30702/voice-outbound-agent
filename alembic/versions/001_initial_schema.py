"""initial_schema

Revision ID: 001
Revises: 
Create Date: 2026-05-07 13:35:23.073562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schema
    op.execute('CREATE SCHEMA IF NOT EXISTS agent_operations')

    # Create campaigns table
    op.create_table(
        'campaigns',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.Enum('draft', 'active', 'paused', 'completed', name='campaignstatus'), nullable=False),
        sa.Column('prompt_template', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('llm_config', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='agent_operations'
    )
    op.create_index('idx_campaign_status', 'campaigns', ['status'], schema='agent_operations')

    # Create contacts table
    op.create_table(
        'contacts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('campaign_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'calling', 'completed', 'failed', 'failed_dnc', name='contactstatus'), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('custom_vars', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['agent_operations.campaigns.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='agent_operations'
    )
    op.create_index('idx_contact_phone', 'contacts', ['phone_number'], schema='agent_operations')
    op.create_index('idx_contact_campaign', 'contacts', ['campaign_id'], schema='agent_operations')
    op.create_index('idx_contact_status', 'contacts', ['status'], schema='agent_operations')
    op.create_index('idx_contact_created', 'contacts', ['created_at'], schema='agent_operations')

    # Create calls table
    op.create_table(
        'calls',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('contact_id', sa.Uuid(), nullable=False),
        sa.Column('retell_call_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('pending', 'calling', 'completed', 'failed', name='callstatus'), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_sec', sa.Integer(), nullable=True),
        sa.Column('disconnect_reason', sa.String(length=100), nullable=True),
        sa.Column('recording_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['contact_id'], ['agent_operations.contacts.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='agent_operations'
    )
    op.create_index('idx_call_contact', 'calls', ['contact_id'], schema='agent_operations')
    op.create_index('idx_call_status', 'calls', ['status'], schema='agent_operations')
    op.create_index('idx_call_created', 'calls', ['created_at'], schema='agent_operations')

    # Create call_transcripts table
    op.create_table(
        'call_transcripts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('call_id', sa.Uuid(), nullable=False),
        sa.Column('raw_transcript', sa.Text(), nullable=True),
        sa.Column('structured_data', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('sentiment', sa.Enum('positive', 'neutral', 'negative', name='sentimentlevel'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['call_id'], ['agent_operations.calls.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('call_id'),
        schema='agent_operations'
    )
    op.create_index('idx_transcript_call', 'call_transcripts', ['call_id'], schema='agent_operations')

    # Create dnc_registry table
    op.create_table(
        'dnc_registry',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('source', sa.Enum('manual', 'national_dnc', 'caller_request', name='dncsource'), nullable=True),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone_number'),
        schema='agent_operations'
    )
    op.create_index('idx_dnc_phone', 'dnc_registry', ['phone_number'], unique=True, schema='agent_operations')


def downgrade() -> None:
    # Drop dnc_registry table
    op.drop_table('dnc_registry', schema='agent_operations')

    # Drop call_transcripts table
    op.drop_index('idx_transcript_call', schema='agent_operations')
    op.drop_table('call_transcripts', schema='agent_operations')

    # Drop calls table
    op.drop_index('idx_call_created', schema='agent_operations')
    op.drop_index('idx_call_status', schema='agent_operations')
    op.drop_index('idx_call_contact', schema='agent_operations')
    op.drop_table('calls', schema='agent_operations')

    # Drop contacts table
    op.drop_index('idx_contact_created', schema='agent_operations')
    op.drop_index('idx_contact_status', schema='agent_operations')
    op.drop_index('idx_contact_campaign', schema='agent_operations')
    op.drop_index('idx_contact_phone', schema='agent_operations')
    op.drop_table('contacts', schema='agent_operations')

    # Drop campaigns table
    op.drop_index('idx_campaign_status', schema='agent_operations')
    op.drop_table('campaigns', schema='agent_operations')

    # Drop schema
    op.execute('DROP SCHEMA IF EXISTS agent_operations')
