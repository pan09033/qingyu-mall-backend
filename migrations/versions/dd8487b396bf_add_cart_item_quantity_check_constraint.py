"""add cart item quantity check constraint

Revision ID: dd8487b396bf
Revises: 0984d0e29c11
Create Date: 2026-09-01 19:05:12.423365

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'dd8487b396bf'
down_revision: Union[str, Sequence[str], None] = '0984d0e29c11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_cart_items_quantity_range",
        "cart_items",
        "quantity BETWEEN 1 AND 99",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_cart_items_quantity_range",
        "cart_items",
        type_="check",
    )
