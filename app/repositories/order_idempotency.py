from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.order import Order
from app.models.order_idempotency_key import (
    OrderIdempotencyKey,
)


def get_order_idempotency_key(
    db: Session,
    user_id: int,
    idempotency_key: str,
) -> OrderIdempotencyKey | None:
    """查询当前用户的一条订单幂等记录。"""

    statement = (
        select(OrderIdempotencyKey)
        .options(
            selectinload(
                OrderIdempotencyKey.order
            ).selectinload(Order.items)
        )
        .where(
            OrderIdempotencyKey.user_id == user_id,
            OrderIdempotencyKey.idempotency_key
            == idempotency_key,
        )
    )
    return db.scalar(statement)


def add_order_idempotency_key(
    db: Session,
    record: OrderIdempotencyKey,
) -> None:
    """把订单幂等记录加入当前数据库会话。"""

    db.add(record)
