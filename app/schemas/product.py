from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
    StringConstraints,
)

ProductName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=30,
    ),
]

class ProductBase(BaseModel):
    """商品响应和后续创建模型可复用的公共字段。"""

    name: ProductName
    price: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
    )
    stock: int = Field(ge=0)
    description: str | None = Field(
        default=None,
        max_length=200,
    )
    image_url: str | None = Field(
        default=None,
        max_length=500,
        description="商品主图地址",
    )
    category_id: int = Field(
        ge=1,
        description="商品分类ID",
    )


class ProductResponse(ProductBase):
    """商品接口的响应模型。"""
    model_config = ConfigDict(
        from_attributes=True,
    )
    id: int

    @field_serializer("price", when_used="json")
    def serialize_price(self, price: Decimal) -> float:
        """保持现有 JSON 数字格式，同时在校验与计算阶段使用 Decimal。"""

        return float(price)


class ProductUpdate(BaseModel):
    """商品部分更新请求模型。"""

    name: ProductName | None = None
    price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2,
    )
    stock: int | None = Field(
        default=None,
        ge=0,
    )
    description: str | None = Field(
        default=None,
        max_length=200,
    )
    image_url: str | None = Field(
        default=None,
        max_length=500,
        description="商品主图地址，传 null 可删除图片",
    )
    category_id: int | None = Field(
        default=None,
        ge=1,
    )
    @field_validator(
        "name",
        "price",
        "stock",
        "category_id",
    )
    @classmethod
    def reject_null(
        cls,
        value: ProductName | Decimal | int | None,
    ) -> ProductName | Decimal | int:
        """更新字段可以省略，但不能明确传入 null。"""
        if value is None:
            raise ValueError("更新字段不能为 null")

        return value

    @model_validator(mode="after")
    def require_update_field(self) -> "ProductUpdate":
        """PATCH 请求至少提供一个需要修改的字段。"""

        if not self.model_fields_set:
            raise ValueError("至少需要提供一个更新字段")

        return self


class ProductCreate(ProductBase):
    """商品创建请求模型。"""


class ProductListResponse(BaseModel):
    """商品列表接口的响应模型。"""

    items: list[ProductResponse]
    total: int
    skip: int
    limit: int
