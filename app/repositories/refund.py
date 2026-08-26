from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.refund_request import RefundRequest


def build_admin_refund_filters(
    user_id: int | None,
    refund_status: str | None,
) -> list:
    """构建管理员退款列表的动态筛选条件。"""

    conditions = []

    # 核心练习区：
    # 1. user_id 有值时，加入“用户编号相等”的条件。
    if user_id is not None:
        conditions.append(
            RefundRequest.user_id == user_id
        )
    # 2. refund_status 有值时，加入“退款状态相等”的条件。
    if refund_status is not None:
        conditions.append(
            RefundRequest.status == refund_status
        )
    return conditions


def get_refund_by_order(
    db: Session,
    order_id: int,
) -> RefundRequest | None:
    """查询订单已有的退款申请。"""

    statement = select(RefundRequest).where(
        RefundRequest.order_id == order_id,
    )
    return db.scalar(statement)


def get_refund_for_update(
    db: Session,
    refund_id: int,
) -> RefundRequest | None:
    """查询并锁定管理员准备审核的退款申请。"""

    statement = (
        select(RefundRequest)
        .where(RefundRequest.id == refund_id)
        .with_for_update()
    )
    return db.scalar(statement)


def add_refund_request(
    db: Session,
    refund_request: RefundRequest,
) -> None:
    """把退款申请加入当前数据库会话。"""

    db.add(refund_request)


def get_admin_refunds(
    db: Session,
    user_id: int | None,
    refund_status: str | None,
    skip: int,
    limit: int,
) -> Sequence[RefundRequest]:
    """管理员分页查询退款申请。"""

    conditions = build_admin_refund_filters(
        user_id,
        refund_status,
    )
    statement = (
        select(RefundRequest)
        .where(*conditions)
        .order_by(RefundRequest.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return db.scalars(statement).all()


def count_admin_refunds(
    db: Session,
    user_id: int | None,
    refund_status: str | None,
) -> int:
    """统计符合管理员筛选条件的退款申请数量。"""

    conditions = build_admin_refund_filters(
        user_id,
        refund_status,
    )
    statement = select(
        func.count(RefundRequest.id)
    ).where(*conditions)
    return db.scalar(statement) or 0
