"""add webhook events

Revision ID: c2f4e6a8b0d2
Revises: a4b6d3f2e1c0
Create Date: 2026-11-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2f4e6a8b0d2'
down_revision: Union[str, Sequence[str], None] = 'a4b6d3f2e1c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'webhook_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.String(length=128), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id'),
    )
    op.create_index('ix_webhook_events_invoice_id', 'webhook_events', ['invoice_id'])


def downgrade() -> None:
    op.drop_index('ix_webhook_events_invoice_id', table_name='webhook_events')
    op.drop_table('webhook_events')
