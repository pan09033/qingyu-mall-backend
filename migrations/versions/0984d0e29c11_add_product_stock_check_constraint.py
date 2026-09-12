"""add product stock check constraint

Revision ID: 0984d0e29c11
Revises: 3a69f65687db
Create Date: 2026-09-01 18:27:19.582336

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0984d0e29c11'
down_revision: Union[str, Sequence[str], None] = '3a69f65687db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_products_stock_nonnegative",
        "products",
        "stock >= 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_products_stock_nonnegative",
        "products",
        type_="check",
    )
