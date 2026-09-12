from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.order import OrderResponse


class UserBase(BaseModel):
    """创建模型和响应模型共用的用户字段。"""

    name: str = Field(
        min_length=1,
        max_length=20,
        description="用户姓名",
    )
    age: int = Field(
        ge=6,
        le=100,
        description="用户年龄",
    )

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: Any) -> Any:
        """在长度校验前清理姓名两侧空格，并拒绝纯空格姓名。"""
        if not isinstance(value, str):
            return value

        cleaned_name = value.strip()
        if not cleaned_name:
            raise ValueError("用户姓名不能为空")

        return cleaned_name


class UserCreate(UserBase):
    """请求模型：客户端创建或完整替换用户时提交的数据。"""


class UserResponse(UserBase):
    """响应模型：服务器返回给客户端的公开用户数据。"""
    model_config = ConfigDict(
        from_attributes=True,
    )
    id: int
    role: str


class UserUpdate(BaseModel):
    """PATCH 请求模型：字段可以省略，但提供时必须合法。"""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=20,
        description="需要修改的用户姓名",
    )
    age: int | None = Field(
        default=None,
        ge=6,
        le=100,
        description="需要修改的用户年龄",
    )

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: Any) -> Any:
        """PATCH 提供姓名时，同样清理两侧空格。"""
        if not isinstance(value, str):
            return value

        cleaned_name = value.strip()
        if not cleaned_name:
            raise ValueError("用户姓名不能为空")

        return cleaned_name

    @field_validator("name", "age")
    @classmethod
    def reject_null(
            cls,
            value: str | int | None,
    ) -> str | int:
        """允许字段不发送，但拒绝客户端明确发送 null。"""
        if value is None:
            raise ValueError("更新字段不能为 null")

        return value

    @model_validator(mode="after")
    def require_update_field(self) -> "UserUpdate":
        """PATCH 请求至少提供一个需要修改的字段。"""

        if not self.model_fields_set:
            raise ValueError("至少需要提供一个更新字段")

        return self


class UserListResponse(BaseModel):
    """用户列表接口的响应模型。"""

    items: list[UserResponse]
    total: int
    skip: int
    limit: int


class UserWithOrdersResponse(UserResponse):
    """用户详情接口的响应模型。"""
    orders: list[OrderResponse]


class UserRegister(UserBase):
    """注册模型：用户注册时提交的数据。"""
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="登录账号，只允许字母、数字和下划线",
    )
    password: str = Field(
        min_length=6,
        max_length=128,
        description="登录密码，至少 6 个字符",
    )

    @field_validator("username", mode="before")
    @classmethod
    def clean_username(cls, value: Any) -> Any:
        """在长度校验前清理用户名两侧空格，并拒绝纯空格用户名。"""
        if not isinstance(value, str):
            return value
        return value.strip().lower()


class UserRegisterResponse(UserResponse):
    """注册成功后返回的公开用户信息。"""

    username: str


class UserRoleUpdate(BaseModel):
    """管理员修改用户角色时提交的数据。"""

    role: Literal[
        "user",
        "admin",
    ]

