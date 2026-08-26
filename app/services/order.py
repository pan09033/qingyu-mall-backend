from collections.abc import Sequence
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.user import User
from app.models.address import Address
from app.order_status import OrderStatus
from app.repositories.address import get_address_by_user
from app.repositories.cart import (
    clear_cart_items_by_user,
    get_cart_items_by_user,
    lock_user_for_cart_change,
)
from app.repositories.order import (
    add_order,
    get_order_by_id_for_update,
    get_order_by_user,
    get_order_by_user_for_update,
    get_orders_by_user,
)
from app.repositories.user import get_user_by_id
from app.schemas.cart import CartCheckout
from app.schemas.order import (
    OrderCreate,
    OrderItemCreate,
    OrderShippingAddressUpdate,
)
from app.exceptions import (
    ConflictError,
    ResourceNotFoundError,
)
from app.repositories.product import (
    get_products_by_ids_for_update,
)


def get_user_or_404(
    db: Session,
    user_id: int,
) -> User:
    """获取用户；用户不存在时抛出404。"""

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    return user


def get_order_or_404(
    db: Session,
    user_id: int,
    order_id: int,
) -> Order:
    """获取指定用户的订单；订单不存在时抛出404。"""

    order = get_order_by_user(
        db,
        user_id,
        order_id,
    )

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在或不属于该用户",
        )

    return order


def get_user_order_for_update_or_404(
    db: Session,
    user_id: int,
    order_id: int,
) -> Order:
    """查询并锁定当前用户的一条订单。"""

    order = get_order_by_user_for_update(
        db,
        user_id,
        order_id,
    )
    if order is None:
        raise ResourceNotFoundError(
            "订单不存在或不属于该用户"
        )
    return order


def get_admin_order_for_update_or_404(
    db: Session,
    order_id: int,
) -> Order:
    """查询并锁定管理员准备操作的订单。"""

    order = get_order_by_id_for_update(
        db,
        order_id,
    )
    if order is None:
        raise ResourceNotFoundError(
            "订单不存在"
        )
    return order


def create_user_order(
    db: Session,
    user_id: int,
    order_data: OrderCreate,
) -> Order:
    """为指定用户创建订单。"""

    get_user_or_404(db, user_id)
    try:
        address = get_address_by_user(
            db,
            user_id,
            order_data.address_id,
        )
        if address is None:
            raise ResourceNotFoundError(
                "收货地址不存在"
            )

        new_order = build_user_order(
            db,
            user_id,
            address,
            order_data.items,
        )
        db.commit()
        db.refresh(new_order)
    except (ResourceNotFoundError, ConflictError):
        # 业务校验失败时也要回滚，及时释放已获得的商品行锁。
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="订单保存失败",
        ) from error

    return new_order


def build_user_order(
    db: Session,
    user_id: int,
    address: Address,
    item_data_list: Sequence[OrderItemCreate],
) -> Order:
    """构建订单并扣减库存，但不提交事务。"""

    product_ids = [
        item.product_id
        for item in item_data_list
    ]
    products = get_products_by_ids_for_update(
        db,
        product_ids,
    )
    products_by_id = {
        product.id: product
        for product in products
    }

    validated_items = []
    total_amount = Decimal("0.00")

    for item_data in item_data_list:
        product = products_by_id.get(
            item_data.product_id
        )
        if product is None:
            raise ResourceNotFoundError(
                "商品不存在"
            )
        if product.stock < item_data.quantity:
            raise ConflictError(
                f"商品“{product.name}”库存不足"
            )

        validated_items.append(
            (product, item_data)
        )
        total_amount += (
            product.price * item_data.quantity
        )

    new_order = Order(
        user_id=user_id,
        total_amount=total_amount,
        receiver_name=address.receiver_name,
        phone=address.phone,
        province=address.province,
        city=address.city,
        district=address.district,
        detail_address=address.detail_address,
    )

    for product, item_data in validated_items:
        product.stock -= item_data.quantity
        new_order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                unit_price=product.price,
                quantity=item_data.quantity,
            )
        )

    add_order(db, new_order)
    return new_order


def checkout_user_cart(
    db: Session,
    user_id: int,
    checkout_data: CartCheckout,
) -> Order:
    """把购物车商品结算为订单，并在同一事务中清空购物车。"""

    try:
        lock_user_for_cart_change(
            db,
            user_id,
        )

        address = get_address_by_user(
            db,
            user_id,
            checkout_data.address_id,
        )
        if address is None:
            raise ResourceNotFoundError(
                "收货地址不存在"
            )

        cart_items = get_cart_items_by_user(
            db,
            user_id,
        )
        if not cart_items:
            raise ConflictError(
                "购物车为空，不能结算"
            )

        order_items = [
            OrderItemCreate(
                product_id=cart_item.product_id,
                quantity=cart_item.quantity,
            )
            for cart_item in cart_items
        ]
        new_order = build_user_order(
            db,
            user_id,
            address,
            order_items,
        )

        # 这里只标记删除；订单、库存和购物车最后一起提交。
        clear_cart_items_by_user(
            db,
            user_id,
        )
        db.commit()
        db.refresh(new_order)
        return new_order

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="购物车结算失败",
        ) from error


def list_user_orders(
    db: Session,
    user_id: int,
) -> Sequence[Order]:
    """返回指定用户的全部订单。"""

    get_user_or_404(db, user_id)
    return get_orders_by_user(db, user_id)


def cancel_user_order(
    db: Session,
    user_id: int,
    order_id: int,
) -> Order:
    """取消待处理订单并恢复商品库存。"""

    try:
        order = get_user_order_for_update_or_404(
            db,
            user_id,
            order_id,
        )

        if order.status != OrderStatus.PENDING:
            raise ConflictError(
                "当前订单状态不允许取消"
            )

        product_ids = [
            order_item.product_id
            for order_item in order.items
        ]
        products = get_products_by_ids_for_update(
            db,
            product_ids,
        )
        products_by_id = {
            product.id: product
            for product in products
        }

        for order_item in order.items:
            product = products_by_id.get(
                order_item.product_id
            )
            if product is None:
                raise ResourceNotFoundError(
                    "订单关联的商品不存在"
                )
            product.stock += order_item.quantity

        order.status = OrderStatus.CANCELLED

        db.commit()
        db.refresh(order)
    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="订单取消失败",
        ) from error

    return order


def ship_paid_order(
    db: Session,
    order_id: int,
) -> Order:
    """管理员把已付款订单修改为已发货。"""

    try:
        order = get_admin_order_for_update_or_404(
            db,
            order_id,
        )
        if order.status != OrderStatus.PAID:
            raise ConflictError(
                "只有已付款订单可以发货"
            )

        order.status = OrderStatus.SHIPPED
        db.commit()
        db.refresh(order)
        return order

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="订单发货状态更新失败",
        ) from error


def complete_user_order(
    db: Session,
    user_id: int,
    order_id: int,
) -> Order:
    """当前用户确认已发货订单完成。"""

    try:
        order = get_user_order_for_update_or_404(
            db,
            user_id,
            order_id,
        )
        if order.status != OrderStatus.SHIPPED:
            raise ConflictError(
                "只有已发货订单可以确认完成"
            )

        order.status = OrderStatus.COMPLETED
        db.commit()
        db.refresh(order)
        return order

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="订单完成状态更新失败",
        ) from error


def update_order_shipping_address(
    db: Session,
    user_id: int,
    order_id: int,
    address_data: OrderShippingAddressUpdate,
) -> Order:
    """修改当前用户待付款订单的收货地址快照。"""

    try:
        order = get_user_order_for_update_or_404(
            db,
            user_id,
            order_id,
        )
        if order.status != OrderStatus.PENDING:
            raise ConflictError(
                "只有待付款订单可以修改收货地址"
            )

        address = get_address_by_user(
            db,
            user_id,
            address_data.address_id,
        )
        if address is None:
            raise ResourceNotFoundError(
                "收货地址不存在"
            )
        # 把新地址复制到订单快照，不修改原地址簿记录。
        order.receiver_name = address.receiver_name
        order.phone = address.phone
        order.province = address.province
        order.city = address.city
        order.district = address.district
        order.detail_address = address.detail_address

        db.commit()
        db.refresh(order)
        return order

    except (ResourceNotFoundError, ConflictError):
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="订单收货地址修改失败",
        ) from error
