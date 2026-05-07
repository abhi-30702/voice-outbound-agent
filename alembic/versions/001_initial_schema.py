"""Initial schema creation with corrected table names.

Revision ID: 001
Revises:
Create Date: 2026-05-07 13:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial schema."""
    # Create schema
    op.execute("CREATE SCHEMA IF NOT EXISTS agent_operations")

    # Create campaigns table
    op.create_table(
        'campaigns',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'ACTIVE', 'PAUSED', 'COMPLETED', name='campaignstatus'), nullable=False, server_default='DRAFT'),
        sa.Column('prompt_template', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('llm_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_campaign_status', 'status'),
        schema='agent_operations'
    )

    # Create leads table (was contacts)
    op.create_table(
        'leads',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('phone_number', sa.String(20), nullable=False),
        sa.Column('first_name', sa.String(100)),
        sa.Column('last_name', sa.String(100)),
        sa.Column('company', sa.String(255)),
        sa.Column('timezone', sa.String(50), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True)),
        sa.Column('status', sa.Enum('PENDING', 'CALLING', 'COMPLETED', 'FAILED', 'FAILED_DNC', name='contactstatus'), nullable=False, server_default='PENDING'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_retry_at', sa.DateTime(timezone=True)),
        sa.Column('custom_vars', postgresql.JSONB(astext_type=sa.Text())),
        sa.ForeignKeyConstraint(['campaign_id'], ['agent_operations.campaigns.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_lead_phone', 'phone_number'),
        sa.Index('idx_lead_campaign', 'campaign_id'),
        sa.Index('idx_lead_status', 'status'),
        sa.Index('idx_lead_created', 'created_at'),
        schema='agent_operations'
    )

    # Create call_logs table (was calls)
    op.create_table(
        'call_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('retell_call_id', sa.String(255)),
        sa.Column('status', sa.Enum('PENDING', 'CALLING', 'COMPLETED', 'FAILED', name='callstatus'), nullable=False, server_default='PENDING'),
        sa.Column('start_time', sa.DateTime(timezone=True)),
        sa.Column('end_time', sa.DateTime(timezone=True)),
        sa.Column('duration_sec', sa.Integer()),
        sa.Column('disconnect_reason', sa.String(100)),
        sa.Column('recording_url', sa.String(500)),
        sa.ForeignKeyConstraint(['lead_id'], ['agent_operations.leads.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_call_log_lead', 'lead_id'),
        sa.Index('idx_call_log_status', 'status'),
        sa.Index('idx_call_log_created', 'created_at'),
        schema='agent_operations'
    )

    # Create call_transcripts table
    op.create_table(
        'call_transcripts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('call_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('raw_transcript', sa.Text()),
        sa.Column('structured_data', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('sentiment', sa.Enum('POSITIVE', 'NEUTRAL', 'NEGATIVE', name='sentimentlevel')),
        sa.ForeignKeyConstraint(['call_id'], ['agent_operations.call_logs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('call_id'),
        sa.Index('idx_transcript_call', 'call_id'),
        schema='agent_operations'
    )

    # Create dnc_registry table
    op.create_table(
        'dnc_registry',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('phone_number', sa.String(20), nullable=False),
        sa.Column('source', sa.Enum('MANUAL', 'NATIONAL_DNC', 'CALLER_REQUEST', name='dncsource')),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone_number'),
        sa.Index('idx_dnc_phone', 'phone_number', unique=True),
        schema='agent_operations'
    )


def downgrade() -> None:
    """Drop initial schema."""
    op.drop_table('dnc_registry', schema='agent_operations')
    op.drop_table('call_transcripts', schema='agent_operations')
    op.drop_table('call_logs', schema='agent_operations')
    op.drop_table('leads', schema='agent_operations')
    op.drop_table('campaigns', schema='agent_operations')
    op.execute("DROP SCHEMA IF EXISTS agent_operations")
