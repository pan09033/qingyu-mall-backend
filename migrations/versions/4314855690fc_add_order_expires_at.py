"""add_order_expires_at

Revision ID: 4314855690fc
Revises: d2a522900dc3
Create Date: 2026-09-03 00:31:47.267995

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4314855690fc'
down_revision: Union[str, Sequence[str], None] = 'd2a522900dc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "orders",
        sa.Column(
            "expires_at",
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE orders
        SET expires_at = DATE_ADD(created_at, INTERVAL 30 MINUTE)
        WHERE expires_at IS NULL
        """
    )
    op.alter_column(
        "orders",
        "expires_at",
        existing_type=sa.DateTime(),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column(
        "orders",
        "expires_at",
    )
