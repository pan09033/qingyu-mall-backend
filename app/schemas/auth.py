from pydantic import BaseModel,Field


class TokenResponse(BaseModel):
    """登录成功后返回的Token。"""

    access_token: str
    token_type: str

class PasswordChange(BaseModel):
    current_password: str = Field(
        min_length=6,
        max_length=128,
        description="当前密码",
    )

    new_password: str = Field(
        min_length=6,
        max_length=128,
        description="新密码",
    )