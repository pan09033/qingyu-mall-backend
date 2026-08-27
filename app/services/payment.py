from datetime import datetime
from decimal import Decimal
from secrets import compare_digest

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, ResourceNotFoundError
from app.models.payment import Payment
from app.order_status import OrderStatus
from app.payment_status import PaymentStatus
from app.repositories.order import get_order_by_id_for_update
from app.repositories.payment import (
    add_payment,
    get_payment_by_order,
    get_payment_by_user,
    get_payment_for_update,
)
from app.schemas.payment import PaymentSuccessCallback
from app.services.order import get_user_order_for_update_or_404


def get_user_payment_or_404(
    db: Session,
    user_id: int,
    payment_id: int,
) -> Payment:
    """查询当前用户的支付记录。"""

    payment = get_payment_by_user(
        db,
        user_id,
        payment_id,
    )
    if payment is None:
        raise ResourceNotFoundError(
            "支付记录不存在"
        )
    return payment


def simulate_user_payment_success(
    db: Session,
    user_id: int,
    payment_id: int,
) -> Payment:
    """为本地演示生成幂等的支付成功回调。"""

    payment = get_user_payment_or_404(
        db,
        user_id,
        payment_id,
    )
    simulation_secret = "internal-development-simulation"

    return handle_payment_success_callback(
        db,
        PaymentSuccessCallback(
            payment_id=payment.id,
            transaction_no=f"SIMULATED-{payment.id}",
            amount=payment.amount,
        ),
        simulation_secret,
        simulation_secret,
    )


def create_order_payment(
    db: Session,
    user_id: int,
    order_id: int,
) -> Payment:
    """为当前用户的待付款订单创建支付记录。"""

    try:
        order = get_user_order_for_update_or_404(
            db,
            user_id,
            order_id,
        )
        if order.status != OrderStatus.PENDING:
            raise ConflictError(
                "只有待付款订单可以创建支付记录"
            )

        existing_payment = get_payment_by_order(
            db,
            order_id,
        )
        if existing_payment is not None:
            db.commit()
            return existing_payment

        payment = Payment(
            order_id=order.id,
            user_id=user_id,
            amount=order.total_amount,
        )
        add_payment(db, payment)
        db.commit()
        db.refresh(payment)
        return payment

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except IntegrityError as error:
        db.rollback()
        raise ConflictError(
            "该订单已经存在支付记录"
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="支付记录创建失败",
        ) from error


def handle_payment_success_callback(
    db: Session,
    callback_data: PaymentSuccessCallback,
    callback_secret: str,
    expected_secret: str,
) -> Payment:
    """验证并幂等处理模拟支付成功回调。"""

    if not compare_digest(
        callback_secret,
        expected_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="支付回调验证失败",
        )

    try:
        payment = get_payment_for_update(
            db,
            callback_data.payment_id,
        )
        if payment is None:
            raise ResourceNotFoundError(
                "支付记录不存在"
            )

        callback_amount = Decimal(
            callback_data.amount
        ).quantize(Decimal("0.01"))
        if callback_amount != payment.amount:
            raise ConflictError(
                "支付金额与订单金额不一致"
            )

        # 同一交易号的成功回调已经处理过，直接返回原结果。
        if payment.status == PaymentStatus.SUCCESS:
            if (
                payment.transaction_no
                != callback_data.transaction_no
            ):
                raise ConflictError(
                    "支付记录已经由其他交易完成"
                )

            db.commit()
            return payment

        order = get_order_by_id_for_update(
            db,
            payment.order_id,
        )
        if order is None:
            raise ResourceNotFoundError(
                "支付记录关联的订单不存在"
            )
        if order.status != OrderStatus.PENDING:
            raise ConflictError(
                "订单当前状态不允许支付"
            )
        if payment.amount != order.total_amount:
            raise ConflictError(
                "支付记录金额与订单金额不一致"
            )

        payment.status = PaymentStatus.SUCCESS
        payment.transaction_no = (
            callback_data.transaction_no
        )
        payment.paid_at = datetime.now()
        order.status = OrderStatus.PAID

        db.commit()
        db.refresh(payment)
        return payment

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except IntegrityError as error:
        db.rollback()
        raise ConflictError(
            "第三方交易号已经被使用"
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="支付回调处理失败",
        ) from error
