"""create addresses

Revision ID: a1d4c8e72f90
Revises: 3f00ed88ccad
Create Date: 2026-08-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1d4c8e72f90"
down_revision: Union[str, Sequence[str], None] = "3f00ed88ccad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建收货地址表。"""

    op.create_table(
        "addresses",
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
            "receiver_name",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "phone",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "province",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "city",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "district",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "detail_address",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_addresses_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_addresses_user_id",
        "addresses",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """删除收货地址表。"""

    op.drop_index(
        "ix_addresses_user_id",
        table_name="addresses",
    )
    op.drop_table("addresses")
