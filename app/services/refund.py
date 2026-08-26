from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, ResourceNotFoundError
from app.models.refund_request import RefundRequest
from app.order_status import OrderStatus
from app.repositories.refund import (
    add_refund_request,
    get_refund_by_order,
)
from app.schemas.refund import RefundRequestCreate
from app.services.order import get_user_order_for_update_or_404


def create_user_refund_request(
    db: Session,
    user_id: int,
    order_id: int,
    refund_data: RefundRequestCreate,
) -> RefundRequest:
    """为当前用户的已付款未发货订单创建退款申请。"""

    try:
        order = get_user_order_for_update_or_404(
            db,
            user_id,
            order_id,
        )
        if order.status != OrderStatus.PAID:
            raise ConflictError(
                "只有已付款未发货订单可以申请退款"
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
