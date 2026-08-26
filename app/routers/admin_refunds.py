from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.refund_status import RefundStatus
from app.schemas.refund import (
    AdminRefundListResponse,
    RefundRequestResponse,
    RefundReview,
)
from app.services.admin_refund import (
    approve_refund_request,
    list_admin_refunds,
    reject_refund_request,
)


router = APIRouter(
    prefix="/admin/refunds",
    tags=["管理员退款"],
)

Database = Annotated[
    Session,
    Depends(get_db),
]
CurrentAdmin = Annotated[
    User,
    Depends(get_current_admin),
]


@router.get(
    "",
    response_model=AdminRefundListResponse,
)
def get_admin_refund_list(
    _current_admin: CurrentAdmin,
    db: Database,
    user_id: Annotated[
        int | None,
        Query(ge=1, description="申请退款的用户ID"),
    ] = None,
    refund_status: Annotated[
        RefundStatus | None,
        Query(
            alias="status",
            description="退款申请状态",
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
    """管理员分页查看退款申请，可按用户和状态筛选。"""

    items, total = list_admin_refunds(
        db,
        user_id,
        (
            refund_status.value
            if refund_status is not None
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


@router.post(
    "/{refund_id}/approve",
    response_model=RefundRequestResponse,
)
def approve_refund(
    current_admin: CurrentAdmin,
    refund_id: Annotated[int, Path(ge=1)],
    review_data: RefundReview,
    db: Database,
):
    """管理员批准退款并恢复未发货商品库存。"""

    return approve_refund_request(
        db,
        current_admin.id,
        refund_id,
        review_data,
    )


@router.post(
    "/{refund_id}/reject",
    response_model=RefundRequestResponse,
)
def reject_refund(
    current_admin: CurrentAdmin,
    refund_id: Annotated[int, Path(ge=1)],
    review_data: RefundReview,
    db: Database,
):
    """管理员拒绝退款，保留支付结果和已扣减库存。"""

    return reject_refund_request(
        db,
        current_admin.id,
        refund_id,
        review_data,
    )
