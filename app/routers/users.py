from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.schemas.user import (
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
    UserWithOrdersResponse,
)
from app.services.user import (
    get_user_or_404,
    get_user_with_orders_or_404,
    list_users,
    update_user_role as update_user_role_service,
)


router = APIRouter(
    prefix="/users",
    tags=["用户管理"],
    dependencies=[
        Depends(get_current_admin),
    ],
)
Database = Annotated[
    Session,
    Depends(get_db),
]
CurrentAdmin = Annotated[
    User,
    Depends(get_current_admin),
]


@router.get(
    "/",
    response_model=UserListResponse,
)
def get_users(
    db: Database,
    keyname: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=20,
            description="用户姓名",
        ),
    ] = None,
    skip: Annotated[
        int,
        Query(
            ge=0,
            description="跳过的数据数量",
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="返回的数据数量",
        ),
    ] = 10,
):
    items, total = list_users(
        db,
        keyname,
        skip,
        limit,
    )
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get(
    "/{user_id}",
    response_model=UserResponse,
)
def get_user(
    user_id: Annotated[int, Path(ge=1)],
    db: Database,
):
    return get_user_or_404(
        db,
        user_id,
    )


@router.get(
    "/{user_id}/details",
    response_model=UserWithOrdersResponse,
)
def get_user_with_orders(
    user_id: Annotated[int, Path(ge=1)],
    db: Database,
):
    return get_user_with_orders_or_404(
        db,
        user_id,
    )


@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
)
def update_user_role(
    user_id: Annotated[int, Path(ge=1)],
    role_data: UserRoleUpdate,
    current_admin: CurrentAdmin,
    db: Database,
):
    """管理员修改指定用户的角色。"""

    return update_user_role_service(
        db,
        current_admin,
        user_id,
        role_data,
    )
