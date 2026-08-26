from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CartItemCreate(BaseModel):
    """加入购物车请求模型。"""

    product_id: int = Field(
        ge=1,
        description="商品ID",
    )
    quantity: int = Field(
        ge=1,
        le=99,
        description="本次加入的商品数量",
    )


class CartItemUpdate(BaseModel):
    """修改购物车商品数量请求模型。"""

    quantity: int = Field(
        ge=1,
        le=99,
        description="修改后的商品总数量",
    )


class CartCheckout(BaseModel):
    """购物车结算请求模型。"""

    address_id: int = Field(
        ge=1,
        description="当前用户的收货地址编号",
    )


class CartItemResponse(BaseModel):
    """一条购物车商品响应。"""

    id: int
    product_id: int
    product_name: str
    unit_price: Decimal
    stock: int
    quantity: int
    subtotal: Decimal
    created_at: datetime


class CartResponse(BaseModel):
    """完整购物车响应。"""

    items: list[CartItemResponse]
    total_quantity: int
    total_amount: Decimal
