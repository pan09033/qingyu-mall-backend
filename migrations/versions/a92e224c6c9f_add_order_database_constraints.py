"""add order database constraints

Revision ID: a92e224c6c9f
Revises: dd8487b396bf
Create Date: 2026-09-01 22:47:54.580270

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a92e224c6c9f'
down_revision: Union[str, Sequence[str], None] = 'dd8487b396bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_orders_total_amount_nonnegative",
        "orders",
        "total_amount >= 0",
    )
    op.create_check_constraint(
        "ck_orders_status_allowed",
        "orders",
        (
            "status IN ("
            "'pending', "
            "'paid', "
            "'shipped', "
            "'completed', "
            "'cancelled', "
            "'refund_pending', "
            "'refunded'"
            ")"
        ),
    )
    op.create_check_constraint(
        "ck_order_items_quantity_positive",
        "order_items",
        "quantity >= 1",
    )
    op.create_check_constraint(
        "ck_order_items_unit_price_nonnegative",
        "order_items",
        "unit_price >= 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_order_items_unit_price_nonnegative",
        "order_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_order_items_quantity_positive",
        "order_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_orders_status_allowed",
        "orders",
        type_="check",
    )
    op.drop_constraint(
        "ck_orders_total_amount_nonnegative",
        "orders",
        type_="check",
    )
