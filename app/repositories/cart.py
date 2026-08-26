from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.cart_item import CartItem
from app.models.user import User


def lock_user_for_cart_change(
    db: Session,
    user_id: int,
) -> User | None:
    """锁定用户行，让同一用户的购物车修改依次执行。"""

    statement = (
        select(User)
        .where(User.id == user_id)
        .with_for_update()
    )
    return db.scalar(statement)


def get_cart_item_by_user_and_product(
    db: Session,
    user_id: int,
    product_id: int,
) -> CartItem | None:
    """根据用户和商品查询购物车记录。"""

    statement = (
        select(CartItem)
        .options(selectinload(CartItem.product))
        .where(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id,
        )
    )
    return db.scalar(statement)


def get_cart_item_by_user(
    db: Session,
    user_id: int,
    cart_item_id: int,
) -> CartItem | None:
    """按购物车记录ID和用户ID查询，防止越权访问。"""

    statement = (
        select(CartItem)
        .options(selectinload(CartItem.product))
        .where(
            CartItem.id == cart_item_id,
            CartItem.user_id == user_id,
        )
    )
    return db.scalar(statement)


def get_cart_items_by_user(
    db: Session,
    user_id: int,
) -> Sequence[CartItem]:
    """查询当前用户的全部购物车商品。"""

    statement = (
        select(CartItem)
        .options(selectinload(CartItem.product))
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.id.desc())
    )
    return db.scalars(statement).all()


def add_cart_item(
    db: Session,
    cart_item: CartItem,
) -> None:
    """把购物车记录加入数据库会话。"""

    db.add(cart_item)


def remove_cart_item(
    db: Session,
    cart_item: CartItem,
) -> None:
    """删除一条购物车记录。"""

    db.delete(cart_item)


def clear_cart_items_by_user(
    db: Session,
    user_id: int,
) -> None:
    """删除当前用户的全部购物车记录。"""

    statement = delete(CartItem).where(
        CartItem.user_id == user_id,
    )
    db.execute(statement)
