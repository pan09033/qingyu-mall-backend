"""add_refund_request_database_constraints

Revision ID: 41823cc91144
Revises: 64947387d0b8
Create Date: 2026-09-02 15:21:42.497114

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '41823cc91144'
down_revision: Union[str, Sequence[str], None] = '64947387d0b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        "ck_refund_requests_amount_positive",
        "refund_requests",
        "amount > 0",
    )
    op.create_check_constraint(
        "ck_refund_requests_status_allowed",
        "refund_requests",
        (
            "status IN ("
            "'pending', "
            "'waiting_return', "
            "'returning', "
            "'approved', "
            "'rejected'"
            ")"
        ),
    )
    op.create_check_constraint(
        "ck_refund_requests_type_allowed",
        "refund_requests",
        (
            "refund_type IN ("
            "'refund_only', "
            "'return_and_refund'"
            ")"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_refund_requests_type_allowed",
        "refund_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_refund_requests_status_allowed",
        "refund_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_refund_requests_amount_positive",
        "refund_requests",
        type_="check",
    )
