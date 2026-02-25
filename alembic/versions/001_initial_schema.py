"""Initial schema for Digital CTO.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-02-25 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE report_type AS ENUM ('daily_standup', 'weekly_report', 'bayes_alert', 'market_scan', 'morning_brief', 'sprint_report', 'devops_report')")
    op.execute("CREATE TYPE notification_status AS ENUM ('pending', 'sent', 'failed')")

    # Create scheduled_reports table
    op.create_table(
        'scheduled_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('report_type', postgresql.ENUM(name='report_type', create_type=False), nullable=False),
        sa.Column('report_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('notified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notification_status', postgresql.ENUM(name='notification_status', create_type=False), nullable=False, server_default='pending'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create agent_decisions table for architecture advisor
    op.create_table(
        'agent_decisions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('decision_type', sa.String(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('outcome', sa.Text(), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for better query performance
    op.create_index('ix_scheduled_reports_type_created', 'scheduled_reports', ['report_type', 'created_at'])
    op.create_index('ix_agent_decisions_agent_created', 'agent_decisions', ['agent_name', 'created_at'])
    op.create_index('ix_agent_decisions_type_created', 'agent_decisions', ['decision_type', 'created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_agent_decisions_type_created', table_name='agent_decisions')
    op.drop_index('ix_agent_decisions_agent_created', table_name='agent_decisions')
    op.drop_index('ix_scheduled_reports_type_created', table_name='scheduled_reports')

    # Drop tables
    op.drop_table('agent_decisions')
    op.drop_table('scheduled_reports')

    # Drop enum types
    op.execute('DROP TYPE notification_status')
    op.execute('DROP TYPE report_type')
