from collections.abc import Sequence
from threading import BoundedSemaphore
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, ResourceNotFoundError
from app.models.product import Product
from app.product_cache import (
    cache_missing_product,
    cache_product,
    get_cached_product,
    invalidate_product_cache,
    try_acquire_product_cache_rebuild_lock,
    wait_for_product_cache,
    release_product_cache_rebuild_lock,
)
from app.repositories.product import (
    add_product,
    count_order_items_by_product,
    count_products,
    get_product_by_id,
    get_products,
    remove_product,
)
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.services.category import get_category_or_404

# 单个后端进程最多允许20个商品详情请求同时回源。
PRODUCT_DETAIL_DB_MAX_CONCURRENCY = 20

# 所有商品详情请求共用这一组查询名额。
product_detail_db_slots = BoundedSemaphore(
    PRODUCT_DETAIL_DB_MAX_CONCURRENCY
)

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


def get_product_detail(
    db: Session,
    product_id: int,
) -> Product | ProductResponse:
    """优先从 Redis 查询商品详情缓存。"""

    cached_product = get_cached_product(product_id)

    if cached_product is not None:
        return cached_product

    # 缓存未命中，为本次重建尝试生成唯一标识。
    lock_token = uuid4().hex

    # 尝试获得当前商品的缓存重建锁。
    lock_acquired = try_acquire_product_cache_rebuild_lock(
        product_id,
        lock_token,
    )
    # 没有获得锁时，短暂等待其他请求重建商品缓存。
    if not lock_acquired:
        cached_product = wait_for_product_cache(product_id)
        if cached_product is not None:
            return cached_product

    try:
        # 获得锁后再次检查，其他请求可能已经建好了缓存。
        if lock_acquired:
            cached_product = get_cached_product(product_id)
            if cached_product is not None:
                return cached_product

        # 没有查询名额时立即返回，避免请求不断堆积到数据库。
        acquired = product_detail_db_slots.acquire(
            blocking=False
        )
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="商品查询繁忙，请稍后重试",
            )
        # 查询数据库，并缓存商品或不存在标记。
        try:
            try:
                product = get_product_or_404(
                    db,
                    product_id,
                )
            finally:
                # 查到商品、抛出404或查询报错，都归还名额。
                product_detail_db_slots.release()
        except ResourceNotFoundError:
            cache_missing_product(product_id)
            raise

        return cache_product(product)
    finally:
        # 只有获得过锁的请求，才尝试释放自己的锁。
        if lock_acquired:
            release_product_cache_rebuild_lock(
                product_id,
                lock_token,
            )


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
        image_url=product_data.image_url,
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
    invalidate_product_cache(
        [new_product.id]
    )

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

    invalidate_product_cache([product_id])

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

    invalidate_product_cache([product_id])
