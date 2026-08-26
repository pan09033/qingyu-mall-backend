from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.order_item import OrderItem
from app.models.product import Product


def build_product_filters(
    category_id: int | None,
    keyword: str | None,
) -> list:
    """构建商品列表的动态筛选条件。"""

    conditions = []

    if keyword is not None:
        conditions.append(
            Product.name.contains(keyword)
        )

    if category_id is not None:
        conditions.append(
            Product.category_id == category_id
        )
    return conditions


def get_products(
    db: Session,
    category_id: int | None,
    keyword: str | None,
    skip: int,
    limit: int,
) -> Sequence[Product]:
    """根据筛选条件分页查询商品。"""

    conditions = build_product_filters(
        category_id,
        keyword,
    )
    statement = (
        select(Product)
        .where(*conditions)
        .order_by(Product.id)
        .offset(skip)
        .limit(limit)
    )
    return db.scalars(statement).all()


def count_products(
    db: Session,
    category_id: int | None,
    keyword: str | None,
) -> int:
    """统计符合筛选条件的商品数量。"""

    conditions = build_product_filters(
        category_id,
        keyword,
    )
    statement = select(
        func.count(Product.id)
    ).where(*conditions)
    return db.scalar(statement) or 0


def get_product_by_id(
    db: Session,
    product_id: int,
) -> Product | None:
    """根据主键查询商品；不存在时返回 None。"""

    return db.get(
        Product,
        product_id,
    )


def add_product(
    db: Session,
    product: Product,
) -> None:
    """把商品对象加入当前数据库会话。"""

    db.add(product)


def remove_product(
    db: Session,
    product: Product,
) -> None:
    """把商品对象标记为待删除。"""

    db.delete(product)


def count_order_items_by_product(
    db: Session,
    product_id: int,
) -> int:
    """统计商品被历史订单明细引用的数量。"""

    statement = select(
        func.count(OrderItem.id)
    ).where(
        OrderItem.product_id == product_id,
    )
    return db.scalar(statement) or 0


def get_products_by_ids_for_update(
    db: Session,
    product_ids: list[int],
) -> Sequence[Product]:
    """查询并锁定准备下单的商品记录。"""

    statement = (
        select(Product)
        .where(
            Product.id.in_(product_ids)
        )
        .order_by(Product.id)
        .with_for_update()
    )

    return db.scalars(statement).all()
