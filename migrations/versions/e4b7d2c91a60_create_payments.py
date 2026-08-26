"""create payments

Revision ID: e4b7d2c91a60
Revises: d8a13e5f742c
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4b7d2c91a60"
down_revision: Union[str, Sequence[str], None] = "d8a13e5f742c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建支付记录表。"""

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "transaction_no",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_payments_order_id_orders",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_payments_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "order_id",
            name="uq_payments_order_id",
        ),
        sa.UniqueConstraint(
            "transaction_no",
            name="uq_payments_transaction_no",
        ),
    )
    op.create_index(
        "ix_payments_user_id",
        "payments",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """删除支付记录表。"""

    op.drop_index(
        "ix_payments_user_id",
        table_name="payments",
    )
    op.drop_table("payments")
