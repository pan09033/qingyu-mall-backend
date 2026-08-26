from collections.abc import Sequence
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, ResourceNotFoundError
from app.models.cart_item import CartItem
from app.models.product import Product
from app.repositories.cart import (
    add_cart_item,
    clear_cart_items_by_user,
    get_cart_item_by_user,
    get_cart_item_by_user_and_product,
    get_cart_items_by_user,
    lock_user_for_cart_change,
    remove_cart_item,
)
from app.schemas.cart import CartItemCreate, CartItemUpdate


def get_cart_item_or_404(
    db: Session,
    user_id: int,
    cart_item_id: int,
) -> CartItem:
    """查询当前用户的一条购物车记录。"""

    cart_item = get_cart_item_by_user(
        db,
        user_id,
        cart_item_id,
    )
    if cart_item is None:
        raise ResourceNotFoundError(
            "购物车商品不存在"
        )
    return cart_item


def serialize_cart_item(
    cart_item: CartItem,
) -> dict[str, object]:
    """把购物车模型转换成包含商品信息的响应数据。"""

    product = cart_item.product
    return {
        "id": cart_item.id,
        "product_id": product.id,
        "product_name": product.name,
        "unit_price": product.price,
        "stock": product.stock,
        "quantity": cart_item.quantity,
        "subtotal": product.price * cart_item.quantity,
        "created_at": cart_item.created_at,
    }


def serialize_cart(
    cart_items: Sequence[CartItem],
) -> dict[str, object]:
    """计算购物车商品总数和当前总金额。"""

    items = [
        serialize_cart_item(cart_item)
        for cart_item in cart_items
    ]
    total_quantity = sum(
        cart_item.quantity
        for cart_item in cart_items
    )
    total_amount = sum(
        (
            cart_item.product.price * cart_item.quantity
            for cart_item in cart_items
        ),
        start=Decimal("0.00"),
    )

    return {
        "items": items,
        "total_quantity": total_quantity,
        "total_amount": total_amount,
    }


def list_user_cart(
    db: Session,
    user_id: int,
) -> dict[str, object]:
    """返回当前用户的购物车。"""

    cart_items = get_cart_items_by_user(
        db,
        user_id,
    )
    return serialize_cart(cart_items)


def add_product_to_cart(
    db: Session,
    user_id: int,
    cart_data: CartItemCreate,
) -> dict[str, object]:
    """加入商品；商品已存在时累加数量，但不扣减库存。"""

    try:
        lock_user_for_cart_change(db, user_id)

        product = db.get(
            Product,
            cart_data.product_id,
        )
        if product is None:
            raise ResourceNotFoundError(
                "商品不存在"
            )

        cart_item = get_cart_item_by_user_and_product(
            db,
            user_id,
            cart_data.product_id,
        )
        new_quantity = cart_data.quantity
        if cart_item is not None:
            new_quantity += cart_item.quantity

        if new_quantity > product.stock:
            raise ConflictError(
                f"商品“{product.name}”库存不足"
            )

        if cart_item is None:
            cart_item = CartItem(
                user_id=user_id,
                product_id=product.id,
                quantity=new_quantity,
                product=product,
            )
            add_cart_item(db, cart_item)
        else:
            cart_item.quantity = new_quantity

        db.commit()
        db.refresh(cart_item)
        return serialize_cart_item(cart_item)

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except IntegrityError as error:
        db.rollback()
        raise ConflictError(
            "购物车商品添加冲突，请重试"
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="加入购物车失败",
        ) from error


def update_cart_item_quantity(
    db: Session,
    user_id: int,
    cart_item_id: int,
    cart_data: CartItemUpdate,
) -> dict[str, object]:
    """把购物车商品数量修改为请求中的总数量。"""

    try:
        lock_user_for_cart_change(db, user_id)
        cart_item = get_cart_item_or_404(
            db,
            user_id,
            cart_item_id,
        )

        if cart_data.quantity > cart_item.product.stock:
            raise ConflictError(
                f"商品“{cart_item.product.name}”库存不足"
            )

        cart_item.quantity = cart_data.quantity
        db.commit()
        db.refresh(cart_item)
        return serialize_cart_item(cart_item)

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="购物车商品修改失败",
        ) from error


def delete_user_cart_item(
    db: Session,
    user_id: int,
    cart_item_id: int,
) -> None:
    """删除当前用户的一条购物车记录。"""

    try:
        lock_user_for_cart_change(db, user_id)
        cart_item = get_cart_item_or_404(
            db,
            user_id,
            cart_item_id,
        )
        remove_cart_item(db, cart_item)
        db.commit()

    except ResourceNotFoundError:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="购物车商品删除失败",
        ) from error


def clear_user_cart(
    db: Session,
    user_id: int,
) -> None:
    """清空当前用户的购物车。"""

    try:
        lock_user_for_cart_change(db, user_id)
        clear_cart_items_by_user(db, user_id)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="购物车清空失败",
        ) from error
