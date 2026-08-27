"""add product image url

Revision ID: a0c4f6e91b2d
Revises: f2c8a61d930b
Create Date: 2026-08-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a0c4f6e91b2d"
down_revision: Union[str, Sequence[str], None] = "f2c8a61d930b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """给商品增加可选的主图地址。"""

    op.add_column(
        "products",
        sa.Column(
            "image_url",
            sa.String(length=500),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """删除商品主图地址。"""

    op.drop_column("products", "image_url")
