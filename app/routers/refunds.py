from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.refund import (
    RefundRequestCreate,
    RefundRequestResponse,
    ReturnTrackingSubmit,
)
from app.services.refund import (
    create_user_refund_request,
    list_user_refund_requests,
    submit_return_tracking,
)


router = APIRouter(
    prefix="/refunds",
    tags=["退款售后"],
)

Database = Annotated[
    Session,
    Depends(get_db),
]
CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]


@router.get(
    "/",
    response_model=list[RefundRequestResponse],
)
def get_my_refund_requests(
    current_user: CurrentUser,
    db: Database,
):
    """返回当前用户自己的退款申请和审核结果。"""

    return list_user_refund_requests(
        db,
        current_user.id,
    )


@router.post(
    "/orders/{order_id}",
    response_model=RefundRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_refund_request(
    current_user: CurrentUser,
    order_id: Annotated[int, Path(ge=1)],
    refund_data: RefundRequestCreate,
    db: Database,
):
    """为当前用户的已付款未发货订单申请退款。"""

    return create_user_refund_request(
        db,
        current_user.id,
        order_id,
        refund_data,
    )

@router.patch(
    "/{refund_id}/return-tracking",
    response_model=RefundRequestResponse,
)
def submit_return_tracking_info(
    current_user: CurrentUser,
    refund_id: Annotated[int, Path(ge=1)],
    tracking_data: ReturnTrackingSubmit,
    db: Database,
):
    """提交退货物流信息。"""

    return submit_return_tracking(
        db,
        current_user.id,
        refund_id,
        tracking_data,
    )
