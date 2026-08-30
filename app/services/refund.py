from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, ResourceNotFoundError
from app.models.refund_request import RefundRequest
from app.order_status import OrderStatus
from app.refund_status import RefundStatus
from app.refund_type import RefundType
from app.repositories.refund import (
    add_refund_request,
    get_refund_by_order,
    get_refunds_by_user,
    get_refund_for_update,
)
from app.schemas.refund import (
    RefundRequestCreate,
    ReturnTrackingSubmit,
)
from app.services.order import get_user_order_for_update_or_404


def list_user_refund_requests(
    db: Session,
    user_id: int,
) -> Sequence[RefundRequest]:
    """返回当前登录用户自己的退款记录。"""

    return get_refunds_by_user(db, user_id)


def create_user_refund_request(
    db: Session,
    user_id: int,
    order_id: int,
    refund_data: RefundRequestCreate,
) -> RefundRequest:
    """为当前用户的订单创建退款申请。"""

    try:
        order = get_user_order_for_update_or_404(
            db,
            user_id,
            order_id,
        )
        if (
            refund_data.refund_type == RefundType.REFUND_ONLY
            and order.status != OrderStatus.PAID
        ):
            raise ConflictError(
                "仅退款只适用于已付款未发货订单"
            )

        if (
            refund_data.refund_type == RefundType.RETURN_AND_REFUND
            and order.status != OrderStatus.SHIPPED
        ):
            raise ConflictError(
                "退货退款只适用于已发货订单"
            )

        existing_refund = get_refund_by_order(
            db,
            order_id,
        )
        if existing_refund is not None:
            raise ConflictError(
                "该订单已经提交过退款申请"
            )

        refund_request = RefundRequest(
            order_id=order.id,
            user_id=user_id,
            amount=order.total_amount,
            reason=refund_data.reason,
            refund_type=refund_data.refund_type.value,
        )
        order.status = OrderStatus.REFUND_PENDING

        add_refund_request(
            db,
            refund_request,
        )
        db.commit()
        db.refresh(refund_request)
        return refund_request

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except IntegrityError as error:
        db.rollback()
        raise ConflictError(
            "该订单已经提交过退款申请"
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="退款申请创建失败",
        ) from error


def submit_return_tracking(
    db: Session,
    user_id: int,
    refund_id: int,
    tracking_data: ReturnTrackingSubmit,
) -> RefundRequest:
    """当前用户为自己的退款申请提交退货物流。"""

    try:
        refund_request = get_refund_for_update(
            db,
            refund_id,
        )

        if (
            refund_request is None
            or refund_request.user_id != user_id
        ):
            raise ResourceNotFoundError(
                "退款申请不存在"
            )

        if refund_request.status != RefundStatus.WAITING_RETURN:
            raise ConflictError(
                "当前退款状态不能填写退货物流"
            )

        refund_request.return_company = (
            tracking_data.company
        )
        refund_request.return_tracking_number = (
            tracking_data.tracking_number
        )
        refund_request.status = RefundStatus.RETURNING

        db.commit()
        db.refresh(refund_request)
        return refund_request

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise

    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="退货物流提交失败",
        ) from error
