from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class CategoryBase(BaseModel):
    """分类请求和响应共用字段。"""

    name: str = Field(
        min_length=1,
        max_length=30,
        description="商品分类名称",
    )

    description: str | None = Field(
        default=None,
        max_length=200,
        description="分类说明",
    )

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: Any) -> Any:
        """清理分类名称两侧空格并拒绝纯空格。"""
        if not isinstance(value, str):
            return value

        cleaned_name = value.strip()
        if not cleaned_name:
            raise ValueError("商品分类名称不能为空")

        return cleaned_name


class CategoryCreate(CategoryBase):
    """创建分类的请求模型。"""


class CategoryResponse(CategoryBase):
    """分类响应模型。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int


class CategoryListResponse(BaseModel):
    """分类分页列表响应模型。"""

    items: list[CategoryResponse]
    total: int
    skip: int
    limit: int


class CategoryUpdate(BaseModel):
    """修改分类的请求模型。"""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
        description="修改后的分类名称",
    )

    description: str | None = Field(
        default=None,
        max_length=200,
        description="修改后的分类说明",
    )

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: Any) -> Any:
        """提供名称时清除空格，并拒绝 null 和纯空格。"""

        if value is None:
            raise ValueError("商品分类名称不能为 null")

        if not isinstance(value, str):
            return value

        cleaned_name = value.strip()
        if not cleaned_name:
            raise ValueError("商品分类名称不能为空")

        return cleaned_name

    @model_validator(mode="after")
    def require_update_field(self) -> "CategoryUpdate":
        """PATCH 请求至少提供一个需要修改的字段。"""

        if not self.model_fields_set:
            raise ValueError("至少需要提供一个更新字段")

        return self
