from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, ResourceNotFoundError
from app.models.product import Product
from app.repositories.product import (
    add_product,
    count_order_items_by_product,
    count_products,
    get_product_by_id,
    get_products,
    remove_product,
)
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.category import get_category_or_404


def list_products(
    db: Session,
    category_id: int | None,
    keyword: str | None,
    skip: int,
    limit: int,
) -> tuple[Sequence[Product], int]:
    """返回当前页商品和符合条件的商品总数。"""

    items = get_products(
        db,
        category_id,
        keyword,
        skip,
        limit,
    )
    total = count_products(
        db,
        category_id,
        keyword,
    )
    return items, total


def get_product_or_404(
    db: Session,
    product_id: int,
) -> Product:
    """查询商品，不存在时抛出项目统一的 404 业务异常。"""

    product = get_product_by_id(
        db,
        product_id,
    )

    if product is None:
        raise ResourceNotFoundError(
            "商品不存在"
        )

    return product


def create_product(
    db: Session,
    product_data: ProductCreate,
) -> Product:
    """校验商品分类并创建商品。"""

    get_category_or_404(
        db,
        product_data.category_id,
    )

    new_product = Product(
        name=product_data.name,
        price=product_data.price,
        stock=product_data.stock,
        description=product_data.description,
        category_id=product_data.category_id,
    )

    try:
        add_product(
            db,
            new_product,
        )
        db.commit()
        db.refresh(new_product)

    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="商品保存失败",
        ) from error

    return new_product


def update_product(
    db: Session,
    product_id: int,
    product_data: ProductUpdate,
) -> Product:
    """部分修改商品，只更新请求中实际提供的字段。"""

    product = get_product_or_404(
        db,
        product_id,
    )
    update_data = product_data.model_dump(
        exclude_unset=True,
    )

    if "category_id" in update_data:
        get_category_or_404(
            db,
            update_data["category_id"],
        )

    for field_name, new_value in update_data.items():
        setattr(product, field_name, new_value)

    try:
        db.commit()
        db.refresh(product)

    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="商品更新失败",
        ) from error

    return product


def delete_product(
    db: Session,
    product_id: int,
) -> None:
    """删除商品；已有外键引用时拒绝删除。"""

    product = get_product_or_404(
        db,
        product_id,
    )

    if count_order_items_by_product(db, product_id) > 0:
        raise ConflictError(
            "商品已有业务记录，不能删除"
        )

    try:
        remove_product(db, product)
        db.commit()

    except IntegrityError as error:
        db.rollback()
        raise ConflictError(
            "商品已有业务记录，不能删除"
        ) from error

    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="商品删除失败",
        ) from error
