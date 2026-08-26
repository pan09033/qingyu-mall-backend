from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class AddressBase(BaseModel):
    """地址请求和响应共用字段。"""

    receiver_name: str = Field(
        min_length=1,
        max_length=20,
        description="收货人姓名",
    )
    phone: str = Field(
        min_length=6,
        max_length=20,
        description="收货人联系电话",
    )
    province: str = Field(
        min_length=1,
        max_length=30,
        description="省份",
    )
    city: str = Field(
        min_length=1,
        max_length=30,
        description="城市",
    )
    district: str = Field(
        min_length=1,
        max_length=30,
        description="区或县",
    )
    detail_address: str = Field(
        min_length=1,
        max_length=200,
        description="详细地址",
    )

    @field_validator(
        "receiver_name",
        "phone",
        "province",
        "city",
        "district",
        "detail_address",
        mode="before",
    )
    @classmethod
    def clean_text(cls, value: Any) -> Any:
        """清除地址文本两侧空格并拒绝纯空格。"""

        if not isinstance(value, str):
            return value

        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("地址字段不能为空")

        return cleaned_value


class AddressCreate(AddressBase):
    """创建地址请求模型。"""

    is_default: bool = False


class AddressUpdate(BaseModel):
    """修改地址请求模型。"""

    receiver_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=20,
    )
    phone: str | None = Field(
        default=None,
        min_length=6,
        max_length=20,
    )
    province: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    city: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    district: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    detail_address: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    @field_validator(
        "receiver_name",
        "phone",
        "province",
        "city",
        "district",
        "detail_address",
        mode="before",
    )
    @classmethod
    def clean_text(cls, value: Any) -> Any:
        """只要提交了字段，就不允许使用 null 或纯空格。"""

        if value is None:
            raise ValueError("地址字段不能为 null")

        if not isinstance(value, str):
            return value

        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("地址字段不能为空")

        return cleaned_value

    @model_validator(mode="after")
    def require_update_field(self) -> "AddressUpdate":
        """PATCH 请求至少提供一个修改字段。"""

        if not self.model_fields_set:
            raise ValueError("至少需要提供一个更新字段")

        return self


class AddressResponse(AddressBase):
    """地址响应模型。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    user_id: int
    is_default: bool
    created_at: datetime
