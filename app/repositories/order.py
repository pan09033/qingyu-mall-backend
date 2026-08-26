from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.models.order import Order


def build_admin_order_filters(
    user_id: int | None,
    order_status: str | None,
) -> list:
    """构建管理员订单列表的动态筛选条件。"""

    conditions = []

    if user_id is not None:
        conditions.append(
            Order.user_id == user_id
        )

    if order_status is not None:
        conditions.append(
            Order.status == order_status
        )

    return conditions


def get_order_by_user(
    db: Session,
    user_id: int,
    order_id: int,
) -> Order | None:
    """根据用户编号和订单编号查询订单。"""

    statement = (
        select(Order)
        .options(
            selectinload(Order.items)
        )
        .where(
            Order.id == order_id,
            Order.user_id == user_id,
        )
    )

    return db.scalar(statement)


def get_order_by_user_for_update(
    db: Session,
    user_id: int,
    order_id: int,
) -> Order | None:
    """查询并锁定当前用户的一条订单。"""

    statement = (
        select(Order)
        .options(selectinload(Order.items))
        .where(
            Order.id == order_id,
            Order.user_id == user_id,
        )
        .with_for_update()
    )
    return db.scalar(statement)


def get_order_by_id_for_update(
    db: Session,
    order_id: int,
) -> Order | None:
    """供管理员查询并锁定一条订单。"""

    statement = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
        .with_for_update()
    )
    return db.scalar(statement)


def get_orders_by_user(
    db: Session,
    user_id: int,
) -> Sequence[Order]:
    """查询指定用户的全部订单。"""

    statement = (
        select(Order)
        .options(
            selectinload(Order.items)
        )
        .where(Order.user_id == user_id)
        .order_by(Order.id)
    )

    return db.scalars(statement).all()


def add_order(
    db: Session,
    order: Order,
) -> None:
    """把订单对象加入当前数据库会话。"""

    db.add(order)


def get_admin_orders(
    db: Session,
    user_id: int | None,
    order_status: str | None,
    skip: int,
    limit: int,
) -> Sequence[Order]:
    """管理员分页查询订单。"""

    conditions = build_admin_order_filters(
        user_id,
        order_status,
    )
    statement = (
        select(Order)
        .options(selectinload(Order.items))
        .where(*conditions)
        .order_by(Order.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return db.scalars(statement).all()


def count_admin_orders(
    db: Session,
    user_id: int | None,
    order_status: str | None,
) -> int:
    """统计符合管理员筛选条件的订单总数。"""

    conditions = build_admin_order_filters(
        user_id,
        order_status,
    )
    statement = select(
        func.count(Order.id)
    ).where(*conditions)
    return db.scalar(statement) or 0
