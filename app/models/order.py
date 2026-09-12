from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

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
from app.order_status import OrderStatus

if TYPE_CHECKING:
    from app.models.order_item import OrderItem
    from app.models.user import User


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "total_amount >= 0",
            name="ck_orders_total_amount_nonnegative",
        ),
        CheckConstraint(
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
            name="ck_orders_status_allowed",
        ),
    )

    # 订单编号
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    # 所属用户编号，外键指向users.id
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    # 订单所属的用户对象
    user: Mapped["User"] = relationship(
        back_populates="orders",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=OrderStatus.PENDING.value,
        server_default=OrderStatus.PENDING.value,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    # 保存下单时的收货信息快照，之后修改地址不会影响历史订单。
    receiver_name: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    province: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    city: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    district: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    detail_address: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    payment: Mapped["Payment | None"] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

    refund_request: Mapped["RefundRequest | None"] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
