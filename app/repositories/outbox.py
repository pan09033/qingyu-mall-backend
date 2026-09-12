from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.outbox_message import OutboxMessage
from app.outbox_status import OutboxStatus


def add_outbox_message(
    db: Session,
    message: OutboxMessage,
) -> None:
    """把待发送消息加入当前数据库事务，但不在这里提交。"""

    db.add(message)


def get_next_pending_outbox_message_for_update(
    db: Session,
    now: datetime,
) -> OutboxMessage | None:
    """按顺序锁定一条已经可以发送的消息。"""

    statement = (
        select(OutboxMessage)
        .where(
            OutboxMessage.status == OutboxStatus.PENDING,
            OutboxMessage.available_at <= now,
        )
        .order_by(OutboxMessage.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return db.scalar(statement)
