from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Path,
    status,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.payment import (
    PaymentResponse,
    PaymentSuccessCallback,
)
from app.services.payment import (
    create_order_payment,
    get_user_payment_or_404,
    handle_payment_success_callback,
)


router = APIRouter(
    prefix="/payments",
    tags=["支付管理"],
)

Database = Annotated[
    Session,
    Depends(get_db),
]
CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]


@router.post(
    "/orders/{order_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    current_user: CurrentUser,
    order_id: Annotated[int, Path(ge=1)],
    db: Database,
):
    """为当前用户的一条待付款订单创建支付记录。"""

    return create_order_payment(
        db,
        current_user.id,
        order_id,
    )


@router.post(
    "/callback",
    response_model=PaymentResponse,
)
def payment_callback(
    callback_data: PaymentSuccessCallback,
    callback_secret: Annotated[
        str,
        Header(alias="X-Payment-Secret"),
    ],
    db: Database,
):
    """模拟第三方支付平台的支付成功回调。"""

    return handle_payment_success_callback(
        db,
        callback_data,
        callback_secret,
        settings.payment_callback_secret,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
)
def get_payment(
    current_user: CurrentUser,
    payment_id: Annotated[int, Path(ge=1)],
    db: Database,
):
    """查询当前用户的一条支付记录。"""

    return get_user_payment_or_404(
        db,
        current_user.id,
        payment_id,
    )
