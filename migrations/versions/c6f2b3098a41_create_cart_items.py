"""create cart items

Revision ID: c6f2b3098a41
Revises: a1d4c8e72f90
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6f2b3098a41"
down_revision: Union[str, Sequence[str], None] = "a1d4c8e72f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建购物车明细表。"""

    op.create_table(
        "cart_items",
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
            "product_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_cart_items_product_id_products",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_cart_items_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "product_id",
            name="uq_cart_items_user_id_product_id",
        ),
    )
    op.create_index(
        "ix_cart_items_product_id",
        "cart_items",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "ix_cart_items_user_id",
        "cart_items",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """删除购物车明细表。"""

    op.drop_index(
        "ix_cart_items_user_id",
        table_name="cart_items",
    )
    op.drop_index(
        "ix_cart_items_product_id",
        table_name="cart_items",
    )
    op.drop_table("cart_items")
