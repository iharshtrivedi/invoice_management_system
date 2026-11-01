"""add invoice email delivery status

Revision ID: a4b6d3f2e1c0
Revises: a9085d2f8e9f
Create Date: 2026-11-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4b6d3f2e1c0"
down_revision: Union[str, Sequence[str], None] = "a9085d2f8e9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    email_status = sa.Enum(
        "not_sent", "queued", "sent", "failed", name="email_status_enum"
    )
    email_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "invoices",
        sa.Column(
            "email_status",
            email_status,
            nullable=False,
            server_default="not_sent",
        ),
    )
    op.add_column("invoices", sa.Column("email_task_id", sa.String(length=50)))
    op.create_index("ix_invoices_email_task_id", "invoices", ["email_task_id"])
    op.alter_column("invoices", "email_status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_invoices_email_task_id", table_name="invoices")
    op.drop_column("invoices", "email_task_id")
    op.drop_column("invoices", "email_status")
    sa.Enum(name="email_status_enum").drop(op.get_bind(), checkfirst=True)
