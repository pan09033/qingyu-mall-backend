import logging
from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.exc import (
    IntegrityError,
    SQLAlchemyError,
)
from sqlalchemy.orm import Session

from app.exceptions import (
    ConflictError,
    ResourceNotFoundError,
)
from app.models.category import Category
from app.repositories.category import (
    add_category,
    count_categories,
    count_products_by_category,
    get_category_by_id,
    get_category_by_name,
    get_categories,
    remove_category,
)
from app.schemas.category import CategoryCreate, CategoryUpdate


logger = logging.getLogger(__name__)


def get_category_or_404(
    db: Session,
    category_id: int,
) -> Category:
    """查询分类，不存在时抛出404。"""

    category = get_category_by_id(
        db,
        category_id,
    )

    if category is None:
        raise ResourceNotFoundError(
            "商品分类不存在"
        )

    return category


def list_categories(
    db: Session,
    skip: int,
    limit: int,
) -> tuple[Sequence[Category], int]:
    """返回当前页分类和分类总数。"""

    items = get_categories(
        db,
        skip,
        limit,
    )

    total = count_categories(db)

    return items, total


def create_category(
    db: Session,
    category_data: CategoryCreate,
) -> Category:
    """创建商品分类。"""

    existing_category = get_category_by_name(
        db,
        category_data.name,
    )

    if existing_category is not None:
        logger.warning(
            "商品分类创建失败，名称已存在：name=%s",
            category_data.name,
        )

        raise ConflictError(
            "商品分类名称已存在"
        )

    new_category = Category(
        name=category_data.name,
        description=category_data.description,
    )

    try:
        add_category(
            db,
            new_category,
        )
        db.commit()
        db.refresh(new_category)

        logger.info(
            "商品分类创建成功：category_id=%s name=%s",
            new_category.id,
            new_category.name,
        )

    except IntegrityError as error:
        db.rollback()

        logger.warning(
            "商品分类创建失败，数据库检测到重复名称："
            "name=%s",
            category_data.name,
        )

        raise ConflictError(
            "商品分类名称已存在"
        ) from error

    except SQLAlchemyError as error:
        db.rollback()

        logger.exception(
            "商品分类创建发生数据库错误：name=%s",
            category_data.name,
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="商品分类创建失败",
        ) from error

    return new_category

def update_category(
    db: Session,
    category_id: int,
    category_data: CategoryUpdate,
) -> Category:
    """修改商品分类。"""

    category = get_category_or_404(
        db,
        category_id,
    )

    update_data = category_data.model_dump(
        exclude_unset=True,
    )

    if "name" in update_data:
        existing_category = get_category_by_name(
            db,
            update_data["name"],
        )

        if (
            existing_category is not None
            and existing_category.id != category.id
        ):
            raise ConflictError(
                "商品分类名称已存在"
            )

    for field, value in update_data.items():
        setattr(category, field, value)

    try:
        db.commit()
        db.refresh(category)

    except IntegrityError as error:
        db.rollback()

        raise ConflictError(
            "商品分类名称已存在"
        ) from error

    except SQLAlchemyError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="商品分类修改失败",
        ) from error

    return category

def delete_category(
    db: Session,
    category_id: int,
) -> None:
    """删除商品分类。"""

    category = get_category_or_404(
        db,
        category_id,
    )
    product_count = count_products_by_category(
        db,
        category_id,
    )

    if product_count > 0:
        raise ConflictError(
            "该分类下存在商品，不能删除"
        )

    try:
        remove_category(
            db,
            category,
        )
        db.commit()

    except IntegrityError as error:
        db.rollback()

        raise ConflictError(
            "该分类下存在商品，不能删除"
        ) from error

    except SQLAlchemyError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="商品分类删除失败",
        ) from error

