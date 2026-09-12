from decimal import Decimal

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.outbox_message import OutboxMessage
from app.models.product import Product
from app.outbox_status import OutboxStatus


def add_checkout_product(
    db: Session,
    stock: int = 5,
    price: Decimal = Decimal("120.00"),
) -> int:
    """创建购物车结算测试商品。"""

    category = db.scalar(
        select(Category).where(
            Category.name == "结算测试分类",
        )
    )
    if category is None:
        category = Category(name="结算测试分类")
        db.add(category)
        db.flush()

    product = Product(
        name="结算测试商品",
        price=price,
        stock=stock,
        description="结算测试",
        category_id=category.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product.id


def test_checkout_creates_order_reduces_stock_and_clears_cart(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """结算应创建订单、扣库存并在同一事务中清空购物车。"""

    product_id = add_checkout_product(db_session)
    add_response = client.post(
        "/cart/items",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "quantity": 2,
        },
    )
    assert add_response.status_code == 201

    response = client.post(
        "/cart/checkout",
        headers=auth_headers,
        json={
            "address_id": shipping_address_id,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    order_data = response.json()
    assert order_data["total_amount"] == "240.00"
    assert order_data["receiver_name"] == "订单测试用户"
    assert order_data["detail_address"] == "科技园1号"
    assert len(order_data["items"]) == 1

    db_session.expire_all()
    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.stock == 3

    outbox_message = db_session.scalar(
        select(OutboxMessage).where(
            OutboxMessage.order_id == order_data["id"],
        )
    )
    assert outbox_message is not None
    assert outbox_message.status == OutboxStatus.PENDING

    cart_response = client.get(
        "/cart/",
        headers=auth_headers,
    )
    assert cart_response.json()["items"] == []


def test_order_keeps_address_snapshot_after_address_update(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """修改地址簿不会改变已经创建的订单地址。"""

    product_id = add_checkout_product(db_session)
    client.post(
        "/cart/items",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "quantity": 1,
        },
    )
    checkout_response = client.post(
        "/cart/checkout",
        headers=auth_headers,
        json={"address_id": shipping_address_id},
    )
    order_id = checkout_response.json()["id"]

    update_response = client.patch(
        f"/addresses/{shipping_address_id}",
        headers=auth_headers,
        json={
            "detail_address": "后来修改的地址",
        },
    )
    assert update_response.status_code == 200

    order_response = client.get(
        f"/orders/{order_id}",
        headers=auth_headers,
    )
    assert order_response.status_code == 200
    assert order_response.json()["detail_address"] == "科技园1号"


def test_checkout_rejects_empty_cart(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
) -> None:
    """购物车为空时不能创建订单。"""

    response = client.post(
        "/cart/checkout",
        headers=auth_headers,
        json={"address_id": shipping_address_id},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "购物车为空，不能结算",
    }


def test_checkout_rechecks_stock_and_keeps_cart_on_failure(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """库存变化导致结算失败时，不扣库存、不清空购物车。"""

    product_id = add_checkout_product(
        db_session,
        stock=2,
    )
    client.post(
        "/cart/items",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "quantity": 2,
        },
    )

    db_session.expire_all()
    product = db_session.get(Product, product_id)
    assert product is not None
    product.stock = 1
    db_session.commit()

    response = client.post(
        "/cart/checkout",
        headers=auth_headers,
        json={"address_id": shipping_address_id},
    )
    assert response.status_code == status.HTTP_409_CONFLICT

    cart_response = client.get(
        "/cart/",
        headers=auth_headers,
    )
    assert cart_response.json()["total_quantity"] == 2

    db_session.expire_all()
    assert db_session.get(Product, product_id).stock == 1
