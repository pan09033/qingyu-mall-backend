"""add_outbox_messages

Revision ID: b67d4f982ca1
Revises: 4314855690fc
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b67d4f982ca1"
down_revision: Union[str, Sequence[str], None] = "4314855690fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the transactional outbox table."""

    op.create_table(
        "outbox_messages",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "payload",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "available_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.CheckConstraint(
            "retry_count >= 0",
            name="ck_outbox_messages_retry_count_nonnegative",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="ck_outbox_messages_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_outbox_messages_order_id_orders",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "order_id",
            "event_type",
            name="uq_outbox_messages_order_id_event_type",
        ),
    )
    op.create_index(
        "ix_outbox_messages_status_available_at",
        "outbox_messages",
        ["status", "available_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the transactional outbox table."""

    op.drop_index(
        "ix_outbox_messages_status_available_at",
        table_name="outbox_messages",
    )
    op.drop_table("outbox_messages")
