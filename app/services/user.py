import logging
from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ResourceNotFoundError
from app.models.user import User
from app.repositories.user import (
    count_users,
    get_user_by_id,
    get_user_with_orders_by_id,
    get_users,
)
from app.schemas.user import UserRoleUpdate


logger = logging.getLogger(__name__)


def list_users(
    db: Session,
    keyname: str | None,
    skip: int,
    limit: int,
) -> tuple[Sequence[User], int]:
    """返回管理员当前页用户和符合条件的用户总数。"""

    items = get_users(
        db,
        keyname,
        skip,
        limit,
    )
    total = count_users(
        db,
        keyname,
    )
    return items, total


def get_user_or_404(
    db: Session,
    user_id: int,
) -> User:
    """查询用户，不存在时抛出项目统一的 404 业务异常。"""

    user = get_user_by_id(
        db,
        user_id,
    )
    if user is None:
        raise ResourceNotFoundError(
            "用户不存在"
        )
    return user


def get_user_with_orders_or_404(
    db: Session,
    user_id: int,
) -> User:
    """查询用户及其订单，不存在时抛出404。"""

    user = get_user_with_orders_by_id(
        db,
        user_id,
    )
    if user is None:
        raise ResourceNotFoundError(
            "用户不存在"
        )
    return user


def update_user_role(
    db: Session,
    current_admin: User,
    user_id: int,
    role_data: UserRoleUpdate,
) -> User:
    """管理员修改用户角色，并禁止取消自己的管理员权限。"""

    user = get_user_or_404(
        db,
        user_id,
    )
    if (
        user.id == current_admin.id
        and role_data.role != "admin"
    ):
        logger.warning(
            "管理员尝试取消自己的权限：admin_id=%s",
            current_admin.id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能取消自己的管理员权限",
        )

    old_role = user.role
    user.role = role_data.role

    try:
        db.commit()
        db.refresh(user)

    except SQLAlchemyError as error:
        db.rollback()
        logger.exception(
            "管理员修改用户角色失败："
            "admin_id=%s user_id=%s requested_role=%s",
            current_admin.id,
            user.id,
            role_data.role,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户角色修改失败",
        ) from error

    logger.info(
        "管理员修改用户角色："
        "admin_id=%s user_id=%s old_role=%s new_role=%s",
        current_admin.id,
        user.id,
        old_role,
        user.role,
    )
    return user
