from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.refund_type import RefundType


class RefundRequestCreate(BaseModel):
    """用户申请退款的请求模型。"""

    refund_type: RefundType = Field(
        default=RefundType.REFUND_ONLY,
        description="退款类型",
    )

    reason: str = Field(
        min_length=2,
        max_length=200,
        description="退款原因",
    )

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("退款原因不能为空")
        return cleaned_value


class ReturnTrackingSubmit(BaseModel):
    """用户提交退货物流时的请求数据。"""

    company: str = Field(
        min_length=2,
        max_length=50,
        description="物流公司",
    )
    tracking_number: str = Field(
        min_length=5,
        max_length=50,
        description="退货物流单号",
    )


class RefundRequestResponse(BaseModel):
    """退款申请响应模型。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    order_id: int
    user_id: int
    amount: Decimal
    reason: str
    status: str
    refund_type: RefundType
    reviewer_id: int | None
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None
    return_company: str | None = None
    return_tracking_number: str | None = None


class RefundReview(BaseModel):
    """管理员审核退款申请时提交的备注。"""

    review_note: str | None = Field(
        default=None,
        max_length=200,
        description="管理员审核备注",
    )


class AdminRefundListResponse(BaseModel):
    """管理员退款申请分页列表。"""

    items: list[RefundRequestResponse]
    total: int
    skip: int
    limit: int
