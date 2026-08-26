from pwdlib import PasswordHash
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import jwt

from app.config import settings

# 创建密码哈希工具，使用当前推荐的安全算法。
password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """将明文密码转换为不可逆的密码哈希。"""

    return password_hash.hash(plain_password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """检查用户输入的密码是否与数据库哈希匹配。"""

    return password_hash.verify(
        plain_password,
        hashed_password,
    )

# 用户不存在时也执行一次密码验证，减少通过响应时间猜测账号的风险。
DUMMY_HASH = password_hash.hash(
    "dummy-password-for-timing-protection"
)

def create_access_token(subject: str) -> str:
    """创建有过期时间的JWT访问令牌。"""

    expire_time = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=settings.access_token_expire_minutes,
        )
    )

    payload = {
        # sub表示Token对应的用户，这里保存唯一用户名。
        "sub": subject,
        # exp表示Token过期时间。
        "exp": expire_time,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )