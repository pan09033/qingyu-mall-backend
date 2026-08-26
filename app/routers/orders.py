from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Path,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.order import (
    OrderCreate,
    OrderResponse,
    OrderShippingAddressUpdate,
)
from app.services.order import (
    cancel_user_order,
    complete_user_order,
    create_user_order,
    get_order_or_404,
    list_user_orders,
    ship_paid_order,
    update_order_shipping_address,
)
from app.dependencies import (
    get_current_admin,
    get_current_user,
)
from app.models.user import User

router = APIRouter(
    # 订单是独立资源，统一使用 /orders 作为路径前缀。
    # 当前用户由 JWT 解析得到，不再让客户端在路径中指定 user_id。
    prefix="/orders",
    tags=["订单管理"],
)

# 为每个接口注入一份独立的数据库会话。
Database = Annotated[
    Session,
    Depends(get_db),
]
CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]
AdminUser = Annotated[
    User,
    Depends(get_current_admin),
]

@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_order(
    current_user: CurrentUser,
    order_data: OrderCreate,
    db: Database,
):
    """接收参数，具体创建逻辑交给Service。"""

    return create_user_order(
        db,
        current_user.id,
        order_data,
    )


@router.get(
    "/",
    response_model=list[OrderResponse],
)
def get_orders(
    current_user: CurrentUser,
    db: Database,
):
    """返回指定用户的订单列表。"""

    return list_user_orders(db,  current_user.id,)


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
)
def get_order(
    current_user: CurrentUser,
    order_id: Annotated[int, Path(ge=1)],
    db: Database,
):
    """返回指定用户的一条订单。"""

    return get_order_or_404(
        db,
        current_user.id,
        order_id,
    )

@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
)
def cancel_order(
    current_user: CurrentUser,
    order_id: Annotated[
        int,
        Path(ge=1),
    ],
    db: Database,
):
    """取消当前用户的待处理订单。"""

    return cancel_user_order(
        db,
        current_user.id,
        order_id,
    )


@router.post(
    "/{order_id}/ship",
    response_model=OrderResponse,
)
def ship_order(
    _admin_user: AdminUser,
    order_id: Annotated[
        int,
        Path(ge=1),
    ],
    db: Database,
):
    """管理员把已付款订单修改为已发货。"""

    return ship_paid_order(
        db,
        order_id,
    )


@router.post(
    "/{order_id}/complete",
    response_model=OrderResponse,
)
def complete_order(
    current_user: CurrentUser,
    order_id: Annotated[
        int,
        Path(ge=1),
    ],
    db: Database,
):
    """当前用户确认自己的已发货订单完成。"""

    return complete_user_order(
        db,
        current_user.id,
        order_id,
    )


@router.patch(
    "/{order_id}/shipping-address",
    response_model=OrderResponse,
)
def change_order_shipping_address(
    current_user: CurrentUser,
    order_id: Annotated[
        int,
        Path(ge=1),
    ],
    address_data: OrderShippingAddressUpdate,
    db: Database,
):
    """修改当前用户待付款订单的收货地址。"""

    return update_order_shipping_address(
        db,
        current_user.id,
        order_id,
        address_data,
    )
