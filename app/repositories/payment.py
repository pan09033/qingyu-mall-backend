from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Payment


def get_payment_by_order(
    db: Session,
    order_id: int,
) -> Payment | None:
    """查询订单已有的支付记录。"""

    statement = select(Payment).where(
        Payment.order_id == order_id,
    )
    return db.scalar(statement)


def get_payment_by_order_for_update(
    db: Session,
    order_id: int,
) -> Payment | None:
    """根据订单查询并锁定支付记录。"""

    statement = (
        select(Payment)
        .where(Payment.order_id == order_id)
        .with_for_update()
    )
    return db.scalar(statement)


def get_payment_by_user(
    db: Session,
    user_id: int,
    payment_id: int,
) -> Payment | None:
    """查询属于当前用户的一条支付记录。"""

    statement = select(Payment).where(
        Payment.id == payment_id,
        Payment.user_id == user_id,
    )
    return db.scalar(statement)


def get_payment_for_update(
    db: Session,
    payment_id: int,
) -> Payment | None:
    """查询并锁定支付记录，防止重复处理回调。"""

    statement = (
        select(Payment)
        .where(Payment.id == payment_id)
        .with_for_update()
    )
    return db.scalar(statement)


def add_payment(
    db: Session,
    payment: Payment,
) -> None:
    """把支付记录加入当前数据库会话。"""

    db.add(payment)
