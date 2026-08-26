from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.order import Order
from app.repositories.order import (
    count_admin_orders,
    get_admin_orders,
)


def list_admin_orders(
    db: Session,
    user_id: int | None,
    order_status: str | None,
    skip: int,
    limit: int,
) -> tuple[Sequence[Order], int]:
    """返回管理员当前页订单和符合条件的总数。"""

    items = get_admin_orders(
        db,
        user_id,
        order_status,
        skip,
        limit,
    )
    total = count_admin_orders(
        db,
        user_id,
        order_status,
    )
    return items, total
