from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentSuccessCallback(BaseModel):
    """模拟第三方平台支付成功回调。"""

    payment_id: int = Field(ge=1)
    transaction_no: str = Field(
        min_length=1,
        max_length=100,
        description="第三方支付平台交易号",
    )
    amount: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
    )


class PaymentResponse(BaseModel):
    """支付记录响应模型。"""

    id: int
    order_id: int
    user_id: int
    amount: Decimal
    status: str
    transaction_no: str | None
    created_at: datetime
    paid_at: datetime | None
