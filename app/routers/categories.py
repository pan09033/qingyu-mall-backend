from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.schemas.category import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)
from app.services.category import (
    create_category,
    delete_category,
    get_category_or_404,
    list_categories,
    update_category,
)


router = APIRouter(
    prefix="/categories",
    tags=["商品分类"],
)

Database = Annotated[
    Session,
    Depends(get_db),
]


@router.get(
    "",
    response_model=CategoryListResponse,
)
def get_categories(
    db: Database,
    skip: Annotated[
        int,
        Query(ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 10,
):
    items, total = list_categories(
        db,
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
    "/{category_id}",
    response_model=CategoryResponse,
)
def get_id(
    db: Database,
    category_id: Annotated[
        int,
        Path(ge=1),
    ],
):
    return get_category_or_404(
        db,
        category_id,
    )


@router.post(
    "/",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(get_current_admin),
    ],
)
def create_category_endpoint(
    db: Database,
    category_data: CategoryCreate,
):
    return create_category(
        db,
        category_data,
    )


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    dependencies=[
        Depends(get_current_admin),
    ],
)
def update_category_endpoint(
    category_id: Annotated[
        int,
        Path(ge=1),
    ],
    category_data: CategoryUpdate,
    db: Database,
):
    return update_category(
        db,
        category_id,
        category_data,
    )


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(get_current_admin),
    ],
)
def delete_category_endpoint(
    db: Database,
    category_id: Annotated[
        int,
        Path(ge=1),
    ],
) -> Response:
    delete_category(
        db,
        category_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
