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
from app.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.services.product import (
    create_product as create_product_service,
    delete_product as delete_product_service,
    get_product_detail,
    list_products,
    update_product as update_product_service,
)


router = APIRouter(
    prefix="/products",
    tags=["商品管理"],
)
Database = Annotated[
    Session,
    Depends(get_db),
]


@router.get(
    "/",
    response_model=ProductListResponse,
)
def get_products(
    db: Database,
    category_id: Annotated[
        int | None,
        Query(
            ge=1,
            description="商品分类ID",
        ),
    ] = None,
    keyword: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=30,
            description="商品名称或描述关键词",
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
    items, total = list_products(
        db,
        category_id,
        keyword,
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
    "/{product_id}",
    response_model=ProductResponse,
)
def get_product(
    product_id: Annotated[
        int,
        Path(ge=1),
    ],
    db: Database,
):
    return get_product_detail(
        db,
        product_id,
    )


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
def create_product(
    product_data: ProductCreate,
    db: Database,
):
    return create_product_service(
        db,
        product_data,
    )


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    dependencies=[Depends(get_current_admin)],
)
def update_product(
    product_id: Annotated[int, Path(ge=1)],
    product_data: ProductUpdate,
    db: Database,
):
    return update_product_service(
        db,
        product_id,
        product_data,
    )


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_admin)],
)
def delete_product(
    product_id: Annotated[int, Path(ge=1)],
    db: Database,
):
    delete_product_service(
        db,
        product_id,
    )
    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
