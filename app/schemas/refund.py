from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class RefundRequestCreate(BaseModel):
    """用户申请退款的请求模型。"""

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
    reviewer_id: int | None
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None


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
