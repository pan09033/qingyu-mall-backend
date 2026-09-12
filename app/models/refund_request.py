from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.refund_status import RefundStatus
from app.refund_type import RefundType


class RefundRequest(Base):
    """订单退款申请。"""

    __tablename__ = "refund_requests"
    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_refund_requests_amount_positive",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'pending', "
                "'waiting_return', "
                "'returning', "
                "'approved', "
                "'rejected'"
                ")"
            ),
            name="ck_refund_requests_status_allowed",
        ),
        CheckConstraint(
            (
                "refund_type IN ("
                "'refund_only', "
                "'return_and_refund'"
                ")"
            ),
            name="ck_refund_requests_type_allowed",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey(
            "orders.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=RefundStatus.PENDING.value,
        server_default=RefundStatus.PENDING.value,
        nullable=False,
    )
    refund_type: Mapped[str] = mapped_column(
        String(30),
        default=RefundType.REFUND_ONLY.value,
        server_default=RefundType.REFUND_ONLY.value,
        nullable=False,
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    review_note: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    return_company: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    return_tracking_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    order: Mapped["Order"] = relationship(
        back_populates="refund_request",
    )
