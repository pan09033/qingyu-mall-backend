"""add shipping snapshot to orders

Revision ID: d8a13e5f742c
Revises: c6f2b3098a41
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8a13e5f742c"
down_revision: Union[str, Sequence[str], None] = "c6f2b3098a41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """给订单增加下单时的收货地址快照。"""

    op.add_column(
        "orders",
        sa.Column(
            "receiver_name",
            sa.String(length=20),
            nullable=False,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "phone",
            sa.String(length=20),
            nullable=False,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "province",
            sa.String(length=30),
            nullable=False,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "city",
            sa.String(length=30),
            nullable=False,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "district",
            sa.String(length=30),
            nullable=False,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "detail_address",
            sa.String(length=200),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """删除订单收货地址快照字段。"""

    op.drop_column("orders", "detail_address")
    op.drop_column("orders", "district")
    op.drop_column("orders", "city")
    op.drop_column("orders", "province")
    op.drop_column("orders", "phone")
    op.drop_column("orders", "receiver_name")
