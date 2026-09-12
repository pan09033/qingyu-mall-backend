from datetime import datetime, timedelta

from pydantic import ValidationError
from pika.exceptions import AMQPError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.outbox_message import OutboxMessage
from app.mq.messages import OrderExpirationMessage
from app.mq.publisher import publish_order_expiration
from app.outbox_status import OutboxStatus
from app.repositories.outbox import (
    get_next_pending_outbox_message_for_update,
)


ORDER_EXPIRATION_EVENT_TYPE = "order.expiration"
OUTBOX_MAX_RETRIES = 3
OUTBOX_RETRY_DELAY_SECONDS = 10


def mark_outbox_message_failed(
    message: OutboxMessage,
    error: Exception,
) -> None:
    """记录永久错误，等待后续人工排查。"""

    message.status = OutboxStatus.FAILED
    message.last_error = (
        f"{type(error).__name__}: {error}"
    )


def schedule_outbox_message_retry(
    message: OutboxMessage,
    error: Exception,
    now: datetime,
) -> None:
    """记录临时发送错误，并决定重试或停止。"""

    message.retry_count += 1
    message.last_error = (
        f"{type(error).__name__}: {error}"
    )
    if message.retry_count >= OUTBOX_MAX_RETRIES:
        message.status = OutboxStatus.FAILED
        return

    message.available_at = now + timedelta(
        seconds=OUTBOX_RETRY_DELAY_SECONDS,
    )


def publish_next_outbox_message(
    db: Session,
    now: datetime | None = None,
) -> bool:
    """锁定并处理一条待发送消息；没有消息时返回 False。"""

    current_time = now or datetime.now()

    try:
        message = get_next_pending_outbox_message_for_update(
            db,
            current_time,
        )
        if message is None:
            # 查询已经开启事务，显式结束它以及时释放数据库资源。
            db.rollback()
            return False

        try:
            if message.event_type != ORDER_EXPIRATION_EVENT_TYPE:
                raise ValueError(
                    f"unsupported event type: {message.event_type}"
                )

            order_message = OrderExpirationMessage.model_validate(
                message.payload,
            )
            if order_message.order_id != message.order_id:
                raise ValueError(
                    "payload order_id does not match outbox order_id"
                )
        except (ValidationError, ValueError) as error:
            mark_outbox_message_failed(message, error)
            db.commit()
            return True

        try:
            publish_order_expiration(order_message.order_id)
        except (AMQPError, OSError) as error:
            schedule_outbox_message_retry(
                message,
                error,
                current_time,
            )
            db.commit()
            return True

        message.status = OutboxStatus.SENT
        message.sent_at = current_time
        message.last_error = None
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        raise
