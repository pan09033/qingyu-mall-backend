from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
    StringConstraints,
)

IdempotencyKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]


class OrderItemCreate(BaseModel):
    """创建订单时提交的一项商品。"""

    product_id: int = Field(
        ge=1,
        description="商品编号",
    )

    quantity: int = Field(
        ge=1,
        description="购买数量",
    )


class OrderCreate(BaseModel):
    """创建包含多项商品的订单。"""

    idempotency_key: IdempotencyKey = Field(
        description="本次创建订单请求的幂等键",
    )

    address_id: int = Field(
        ge=1,
        description="当前用户的收货地址编号",
    )

    items: list[OrderItemCreate] = Field(
        min_length=1,
        max_length=50,
        description="订单商品列表",
    )

    @model_validator(mode="after")
    def reject_duplicate_products(self) -> "OrderCreate":
        product_ids = [
            item.product_id
            for item in self.items
        ]

        if len(product_ids) != len(set(product_ids)):
            raise ValueError(
                "同一种商品不能重复提交"
            )

        return self


class OrderShippingAddressUpdate(BaseModel):
    """修改待付款订单收货地址的请求模型。"""

    address_id: int = Field(
        ge=1,
        description="当前用户的新收货地址编号",
    )


class OrderItemResponse(BaseModel):
    """订单中的一项商品响应。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int


class OrderResponse(BaseModel):
    """返回给客户端的完整订单。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    user_id: int
    total_amount: Decimal
    status: str
    receiver_name: str
    phone: str
    province: str
    city: str
    district: str
    detail_address: str
    created_at: datetime
    expires_at: datetime
    items: list[OrderItemResponse]


class AdminOrderListResponse(BaseModel):
    """管理员订单分页列表响应。"""

    items: list[OrderResponse]
    total: int
    skip: int
    limit: int
