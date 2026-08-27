from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class ProductBase(BaseModel):
    """商品响应和后续创建模型可复用的公共字段。"""

    name: str
    price: float = Field(gt=0)
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


class ProductUpdate(BaseModel):
    """商品部分更新请求模型。"""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    price: float | None = Field(
        default=None,
        gt=0,
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

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: Any) -> Any:
        """提供商品名称时，清理两侧空格并拒绝纯空格。"""
        if not isinstance(value, str):
            return value

        cleaned_name = value.strip()
        if not cleaned_name:
            raise ValueError("商品名称不能为空")

        return cleaned_name

    @field_validator(
        "name",
        "price",
        "stock",
        "category_id",
    )
    @classmethod
    def reject_null(
        cls,
        value: str | float | int | None,
    ) -> str | float | int:
        """更新字段可以省略，但不能明确传入 null。"""
        if value is None:
            raise ValueError("更新字段不能为 null")

        return value


class ProductCreate(ProductBase):
    """商品创建请求模型。"""


class ProductListResponse(BaseModel):
    """商品列表接口的响应模型。"""

    items: list[ProductResponse]
    total: int
    skip: int
    limit: int
