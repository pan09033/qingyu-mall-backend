from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product


def get_category_by_id(
    db: Session,
    category_id: int,
) -> Category | None:
    """根据主键查询分类。"""

    return db.get(
        Category,
        category_id,
    )


def get_category_by_name(
    db: Session,
    name: str,
) -> Category | None:
    """根据名称查询分类。"""

    statement = select(Category).where(
        Category.name == name,
    )

    return db.scalar(statement)


def get_categories(
    db: Session,
    skip: int,
    limit: int,
) -> Sequence[Category]:
    """分页查询商品分类。"""

    statement = (
        select(Category)
        .order_by(Category.id)
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(statement).all()


def count_categories(
    db: Session,
) -> int:
    """统计商品分类总数。"""

    statement = select(
        func.count(Category.id)
    )

    return db.scalar(statement) or 0


def add_category(
    db: Session,
    category: Category,
) -> None:
    """把分类对象加入当前数据库会话。"""

    db.add(category)


def remove_category(
    db: Session,
    category: Category,
) -> None:
    """把分类对象标记为待删除。"""
    db.delete(category)


def count_products_by_category(
    db: Session,
    category_id: int,
) -> int:
    """统计指定分类下的商品数量。"""

    statement = select(
        func.count(Product.id)
    ).where(
        Product.category_id == category_id,
    )

    return db.scalar(statement) or 0
