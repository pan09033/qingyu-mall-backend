"""add payment database constraints

Revision ID: 64947387d0b8
Revises: a92e224c6c9f
Create Date: 2026-09-02 00:06:46.725725

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '64947387d0b8'
down_revision: Union[str, Sequence[str], None] = 'a92e224c6c9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_payments_amount_positive",
        "payments",
        "amount > 0",
    )
    op.create_check_constraint(
        "ck_payments_status_allowed",
        "payments",
        (
            "status IN ("
            "'pending', "
            "'success', "
            "'failed', "
            "'refunded'"
            ")"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_payments_status_allowed",
        "payments",
        type_="check",
    )
    op.drop_constraint(
        "ck_payments_amount_positive",
        "payments",
        type_="check",
    )
