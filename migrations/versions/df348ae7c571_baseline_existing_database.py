"""baseline existing database

Revision ID: df348ae7c571
Revises: 
Create Date: 2026-08-02 21:13:17.820467

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df348ae7c571'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """建立最早期商品表，兼容已手工建表并 stamp 的旧环境。"""

    # 这个项目最初在引入 Alembic 前已经手工创建了 products 表，
    # 因而旧环境会直接 stamp 此基线。新克隆的空数据库则需要在这里
    # 创建该表，否则下一条迁移会尝试修改一个不存在的表。
    op.create_table(
        "products",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "price",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
        ),
        sa.Column(
            "stock",
            sa.Integer(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """保留基线之前已经存在的商品表。"""

    # 该 revision 同时服务于旧的已存在数据库，无法可靠判断表由谁创建；
    # 降级到基线之前时保留 products，避免误删旧环境数据。
    pass
