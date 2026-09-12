import logging

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError
from app.models.user import User
from app.repositories.user import (
    add_user,
    count_orders_by_user,
    get_user_by_username,
)
from app.schemas.auth import PasswordChange
from app.schemas.user import UserRegister
from app.security import (
    DUMMY_HASH,
    hash_password,
    verify_password,
)


logger = logging.getLogger(__name__)


def register_user(
    db: Session,
    user_data: UserRegister,
) -> User:
    """注册新用户。"""

    # 注册前检查用户名是否已经存在。
    existing_user = get_user_by_username(
        db,
        user_data.username,
    )

    if existing_user is not None:
        logger.warning(
            "用户注册失败，用户名已存在：username=%s",
            user_data.username,
        )
        raise ConflictError(
            "用户名已存在",
        )

    # 明文密码只在这里短暂使用，转换成哈希后再保存。
    new_user = User(
        name=user_data.name,
        age=user_data.age,
        username=user_data.username,
        hashed_password=hash_password(
            user_data.password,
        ),
    )

    try:
        add_user(db, new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(
            "用户注册成功：user_id=%s username=%s",
            new_user.id,
            new_user.username,
        )
    except IntegrityError as error:
        # 防止两个请求同时注册相同用户名。
        db.rollback()

        logger.warning(
            "用户注册失败，数据库检测到重复用户名：username=%s",
            user_data.username,
        )

        raise ConflictError(
            "用户名已存在",
        ) from error
    except SQLAlchemyError as error:
        db.rollback()

        logger.exception(
            "用户注册发生数据库错误：username=%s",
            user_data.username,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户注册失败",
        ) from error

    return new_user


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User:
    """验证用户名和密码。"""

    normalized_username = username.strip().lower()

    user = get_user_by_username(
        db,
        normalized_username,
    )

    stored_hash = (
        user.hashed_password
        if user is not None and user.hashed_password is not None
        else DUMMY_HASH
    )

    password_is_valid = verify_password(
        password,
        stored_hash,
    )

    if (
        user is None
        or user.hashed_password is None
        or not password_is_valid
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    return user


def delete_user_account(
    db: Session,
    current_user: User,
) -> None:
    """删除无业务记录的账号，并保护订单、支付和退款历史。"""

    if count_orders_by_user(db, current_user.id) > 0:
        raise ConflictError(
            "账号存在订单记录，不能直接删除"
        )

    try:
        db.delete(current_user)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ConflictError(
            "账号存在业务记录，不能直接删除"
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception(
            "用户删除账号失败：user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="账号删除失败",
        ) from error


def update_password(
    db: Session,
    current_user: User,
    password_data : PasswordChange,
) -> None:
    current_password_is_valid = verify_password(
        password_data.current_password,
        current_user.hashed_password,
    )
    if not current_password_is_valid:
        raise HTTPException(
            status_code= status.HTTP_400_BAD_REQUEST,
            detail='当前密码错误'
        )
    if (
        password_data.current_password == password_data.new_password
    ):
        raise ConflictError(
            "新密码不能与当前密码相同"
        )
    current_user.hashed_password = hash_password(
        password_data.new_password
    )
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception(
            "用户修改密码失败：user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=(status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail="密码修改失败"
        ) from error
