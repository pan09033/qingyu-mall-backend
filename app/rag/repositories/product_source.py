from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.product import Product


def get_product_batch_for_knowledge_sync(
    mysql_db: Session,
    after_id: int = 0,
    limit: int = 100,
) -> Sequence[Product]:
    """按商品ID分批读取商品，并提前加载分类。"""

    statement = (
        select(Product)
        .options(
            selectinload(Product.category)
        )
        .where(Product.id > after_id)
        .order_by(Product.id.asc())
        .limit(limit)
    )

    return mysql_db.scalars(statement).all()


def get_product_for_knowledge_sync(
    mysql_db: Session,
    product_id: int,
) -> Product | None:
    """根据商品ID读取商品，并提前加载分类。"""

    # mysql_db：MySQL数据库会话
    # product_id：任务中记录的商品ID
    # statement：查询商品及其分类的语句
    statement = (
        select(Product)
        .options(
            selectinload(Product.category),
        )
        .where(Product.id == product_id)
    )

    return mysql_db.scalar(statement)
