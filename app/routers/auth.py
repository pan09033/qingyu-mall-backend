from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import PasswordChange, TokenResponse
from app.schemas.user import (
    UserRegister,
    UserRegisterResponse,
    UserUpdate,
)
from app.security import create_access_token
from app.services.auth import (
    authenticate_user,
    delete_user_account,
    register_user,
    update_password,
)
from app.services.login_rate_limit import (
    build_login_rate_limit_scope,
    check_login_rate_limit,
    clear_login_failures,
    record_login_failure,
)


router = APIRouter(
    prefix="/auth",
    tags=["用户管理"],
)

Database = Annotated[
    Session,
    Depends(get_db),
]
CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserRegister,
    db: Database,
):
    """用户注册。"""

    return register_user(db, user_data)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    request: Request,
    form_data: Annotated[
        OAuth2PasswordRequestForm,
        Depends(),
    ],
    db: Database,
):
    """验证账号密码并返回 JWT。"""

    client_ip = (
        request.client.host
        if request.client is not None
        else "unknown"
    )

    rate_limit_scope = build_login_rate_limit_scope(
        client_ip,
        form_data.username,
    )
    check_login_rate_limit(rate_limit_scope)

    try:
        user = authenticate_user(
            db,
            form_data.username,
            form_data.password,
        )
    except HTTPException as error:
        if error.status_code == status.HTTP_401_UNAUTHORIZED:
            record_login_failure(rate_limit_scope)

        raise

    clear_login_failures(rate_limit_scope)

    access_token = create_access_token(
        subject=str(user.id),
        hashed_password=user.hashed_password,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=UserRegisterResponse,
)
def get_me(
    current_user: CurrentUser,
):
    """返回当前登录用户。"""

    return current_user


@router.patch(
    "/me",
    response_model=UserRegisterResponse,
)
def update_me(
    user_data: UserUpdate,
    current_user: CurrentUser,
    db: Database,
):
    """修改当前登录用户的公开资料。"""

    update_data = user_data.model_dump(
        exclude_unset=True,
    )

    for field_name, new_value in update_data.items():
        setattr(
            current_user,
            field_name,
            new_value,
        )

    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_me(
    current_user: CurrentUser,
    db: Database,
):
    """删除当前登录账号。"""

    delete_user_account(db, current_user)

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
@router.patch('/me/password',
              status_code= status.HTTP_204_NO_CONTENT)
def update_my_password(
        db : Database,
        current_user: CurrentUser,
        password_data : PasswordChange,
):
    update_password(
        db,
        current_user,
        password_data,
    )
    return Response(
        status_code= status.HTTP_204_NO_CONTENT
    )
