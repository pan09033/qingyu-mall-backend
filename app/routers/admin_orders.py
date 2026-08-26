from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.order_status import OrderStatus
from app.schemas.order import AdminOrderListResponse
from app.services.admin_order import list_admin_orders


router = APIRouter(
    prefix="/admin/orders",
    tags=["管理员订单"],
    dependencies=[Depends(get_current_admin)],
)

Database = Annotated[
    Session,
    Depends(get_db),
]


@router.get(
    "",
    response_model=AdminOrderListResponse,
)
def get_admin_order_list(
    db: Database,
    user_id: Annotated[
        int | None,
        Query(ge=1, description="下单用户ID"),
    ] = None,
    order_status: Annotated[
        OrderStatus | None,
        Query(
            alias="status",
            description="订单状态",
        ),
    ] = None,
    skip: Annotated[
        int,
        Query(ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 10,
):
    items, total = list_admin_orders(
        db,
        user_id,
        (
            order_status.value
            if order_status is not None
            else None
        ),
        skip,
        limit,
    )
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }
