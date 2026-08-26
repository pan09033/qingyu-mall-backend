"""项目中可重复使用的 FastAPI 依赖。"""

from typing import Annotated

import jwt
from fastapi import (
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.exceptions import PermissionDeniedError
from app.models.user import User
from app.repositories.user import get_user_by_id


def pagination_parameters(
    skip: Annotated[
        int,
        Query(ge=0, description="需要跳过的数据数量"),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="最多返回的数据数量"),
    ] = 10,
) -> dict[str, int]:
    """集中校验分页参数，并把结果提供给依赖它的接口。"""
    return {
        "skip": skip,
        "limit": limit,
    }


# 告诉FastAPI：登录获取Token的地址是/auth/login。
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
)


def get_current_user(
    token: Annotated[
        str,
        Depends(oauth2_scheme),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> User:
    """解析JWT并返回当前登录用户。"""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证登录凭证",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[
                settings.jwt_algorithm,
            ],
        )

        # 登录时将用户id以字符串形式保存在sub中。
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception

        user_id = int(subject)
    except (InvalidTokenError, TypeError, ValueError):
        # Token过期、签名错误、格式错误都会返回401。
        raise credentials_exception

    user = get_user_by_id(
        db,
        user_id,
    )

    if user is None or user.username is None:
        raise credentials_exception

    return user


def get_current_admin(
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> User:
    """验证当前用户是否为管理员。"""

    if current_user.role != "admin":
        raise PermissionDeniedError(
            "需要管理员权限",
        )

    return current_user
