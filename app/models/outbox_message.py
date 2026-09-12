from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.outbox_status import OutboxStatus

if TYPE_CHECKING:
    from app.models.order import Order


class OutboxMessage(Base):
    """等待可靠发布到消息队列的数据库消息记录。"""

    __tablename__ = "outbox_messages"
    __table_args__ = (
        UniqueConstraint(
            "order_id",
            "event_type",
            name="uq_outbox_messages_order_id_event_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="ck_outbox_messages_status_allowed",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_outbox_messages_retry_count_nonnegative",
        ),
        Index(
            "ix_outbox_messages_status_available_at",
            "status",
            "available_at",
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
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    payload: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=OutboxStatus.PENDING.value,
        server_default=OutboxStatus.PENDING.value,
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    order: Mapped["Order"] = relationship()
