from datetime import datetime
from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, ResourceNotFoundError
from app.models.order import Order
from app.models.payment import Payment
from app.models.refund_request import RefundRequest
from app.order_status import OrderStatus
from app.payment_status import PaymentStatus
from app.refund_status import RefundStatus
from app.repositories.order import get_order_by_id_for_update
from app.repositories.payment import get_payment_by_order_for_update
from app.repositories.product import get_products_by_ids_for_update
from app.repositories.refund import (
    count_admin_refunds,
    get_admin_refunds,
    get_refund_for_update,
)
from app.schemas.refund import RefundReview, RefundRequestResponse


def list_admin_refunds(
    db: Session,
    user_id: int | None,
    refund_status: str | None,
    skip: int,
    limit: int,
) -> tuple[Sequence[RefundRequest], int]:
    """返回管理员当前页退款申请和符合条件的总数。"""

    items = get_admin_refunds(
        db,
        user_id,
        refund_status,
        skip,
        limit,
    )
    total = count_admin_refunds(
        db,
        user_id,
        refund_status,
    )
    return items, total


def _get_refund_review_context(
    db: Session,
    refund_id: int,
) -> tuple[RefundRequest, Payment, Order]:
    """锁定退款、支付和订单，并完成审核前的共用校验。"""

    refund_request = get_refund_for_update(
        db,
        refund_id,
    )
    if refund_request is None:
        raise ResourceNotFoundError(
            "退款申请不存在"
        )
    if refund_request.status != RefundStatus.PENDING:
        raise ConflictError(
            "该退款申请已经审核"
        )

    payment = get_payment_by_order_for_update(
        db,
        refund_request.order_id,
    )
    if payment is None:
        raise ResourceNotFoundError(
            "订单支付记录不存在"
        )
    if payment.status != PaymentStatus.SUCCESS:
        raise ConflictError(
            "支付记录当前状态不允许退款"
        )

    order = get_order_by_id_for_update(
        db,
        refund_request.order_id,
    )
    if order is None:
        raise ResourceNotFoundError(
            "退款申请关联的订单不存在"
        )
    if order.status != OrderStatus.REFUND_PENDING:
        raise ConflictError(
            "订单当前状态不允许退款"
        )

    return refund_request, payment, order


def approve_refund_request(
    db: Session,
    admin_id: int,
    refund_id: int,
    review_data: RefundReview,
) -> RefundRequestResponse:
    """管理员批准未发货订单的退款申请。"""

    try:
        refund_request, payment, order = (
            _get_refund_review_context(
                db,
                refund_id,
            )
        )

        product_ids = [
            order_item.product_id
            for order_item in order.items
        ]
        products = get_products_by_ids_for_update(
            db,
            product_ids,
        )
        products_by_id = {
            product.id: product
            for product in products
        }

        for order_item in order.items:
            product = products_by_id.get(
                order_item.product_id
            )
            if product is None:
                raise ResourceNotFoundError(
                    "退款订单关联的商品不存在"
                )
            product.stock += order_item.quantity

        refund_request.status = RefundStatus.APPROVED
        order.status = OrderStatus.REFUNDED
        payment.status = PaymentStatus.REFUNDED
        refund_request.reviewer_id = admin_id
        refund_request.review_note = review_data.review_note
        refund_request.reviewed_at = datetime.now()

        db.commit()
        db.refresh(refund_request)
        return RefundRequestResponse.model_validate(
            refund_request
        )

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="退款批准失败",
        ) from error


def reject_refund_request(
    db: Session,
    admin_id: int,
    refund_id: int,
    review_data: RefundReview,
) -> RefundRequestResponse:
    """管理员拒绝退款，订单恢复为已支付状态。"""

    try:
        refund_request, _payment, order = (
            _get_refund_review_context(
                db,
                refund_id,
            )
        )

        # 拒绝退款后，申请结束，订单恢复到已支付状态。
        refund_request.status = RefundStatus.REJECTED
        order.status = OrderStatus.PAID

        # 支付仍然有效，因此不修改支付状态；拒绝退款也不恢复库存。
        refund_request.reviewer_id = admin_id
        refund_request.review_note = review_data.review_note
        refund_request.reviewed_at = datetime.now()

        db.commit()
        db.refresh(refund_request)
        return RefundRequestResponse.model_validate(
            refund_request
        )

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="退款拒绝失败",
        ) from error
