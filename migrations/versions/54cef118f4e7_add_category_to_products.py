"""add category to products

Revision ID: 54cef118f4e7
Revises: e750d2424707
Create Date: 2026-08-20 17:31:30.451597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '54cef118f4e7'
down_revision: Union[str, Sequence[str], None] = 'e750d2424707'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """给商品添加分类，并兼容数据库中的已有商品。"""

    # 第一步：临时允许为空，避免旧商品立即违反非空约束。
    op.add_column(
        "products",
        sa.Column(
            "category_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    # 第二步：创建一个用于接收旧商品的默认分类。
    category_table = sa.table(
        "categories",
        sa.column("name", sa.String(30)),
        sa.column("description", sa.String(200)),
    )
    op.bulk_insert(
        category_table,
        [
            {
                "name": "未分类",
                "description": "迁移前已有商品的默认分类",
            }
        ],
    )

    # 第三步：把所有旧商品关联到“未分类”。
    op.execute(
        sa.text(
            """
            UPDATE products
            SET category_id = (
                SELECT id
                FROM categories
                WHERE name = '未分类'
            )
            WHERE category_id IS NULL
            """
        )
    )

    # 第四步：旧数据回填完成后，再设置为不允许为空。
    op.alter_column(
        "products",
        "category_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # 第五步：添加有明确名称的外键，方便以后回滚。
    op.create_foreign_key(
        "fk_products_category_id_categories",
        "products",
        "categories",
        ["category_id"],
        ["id"],
    )


def downgrade() -> None:
    """移除商品分类关联。"""

    op.drop_constraint(
        "fk_products_category_id_categories",
        "products",
        type_="foreignkey",
    )
    op.drop_column(
        "products",
        "category_id",
    )

    # 删除本次迁移创建的默认分类。
    op.execute(
        sa.text(
            """
            DELETE FROM categories
            WHERE name = '未分类'
            """
        )
    )
