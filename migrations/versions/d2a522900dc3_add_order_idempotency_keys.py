"""add_order_idempotency_keys

Revision ID: d2a522900dc3
Revises: 41823cc91144
Create Date: 2026-09-02 16:40:00.150918

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2a522900dc3'
down_revision: Union[str, Sequence[str], None] = '41823cc91144'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "order_idempotency_keys",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "request_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_order_idempotency_keys_order_id_orders",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_order_idempotency_keys_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "order_id",
            name="uq_order_idempotency_keys_order_id",
        ),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_order_idempotency_keys_user_id_key",
        ),
    )
    op.create_index(
        "ix_order_idempotency_keys_user_id",
        "order_idempotency_keys",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_order_idempotency_keys_user_id",
        table_name="order_idempotency_keys",
    )
    op.drop_table("order_idempotency_keys")
