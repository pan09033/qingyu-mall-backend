from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.outbox_message import OutboxMessage
from app.models.product import Product
from app.order_status import OrderStatus
from app.outbox_status import OutboxStatus
from app.redis_client import redis_client
from app.services import order as order_service
from app.services.order import expire_pending_order


def add_test_product(
    db: Session,
    stock: int = 10,
    name: str = "测试键盘",
    price: Decimal = Decimal("299.00"),
) -> int:
    """直接向测试数据库加入商品，并返回商品编号。"""

    category = db.scalar(
        select(Category).where(
            Category.name == "订单测试分类",
        )
    )

    if category is None:
        category = Category(
            name="订单测试分类",
        )
        db.add(category)
        db.flush()

    product = Product(
        name=name,
        price=price,
        stock=stock,
        description="订单测试商品",
        category_id=category.id,
    )

    db.add(product)
    db.commit()
    db.refresh(product)
    return product.id


def create_test_order(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db: Session,
) -> int:
    """创建一笔用于数据库约束测试的正常订单。"""

    product_id = add_test_product(db)
    response = client.post(
        "/orders/",
        headers=auth_headers,
        json={
            "idempotency_key": f"constraint-{product_id}",
            "address_id": shipping_address_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                },
            ],
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_expiration_test_order(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db: Session,
) -> tuple[int, int]:
    """创建一笔用于测试订单过期处理的待付款订单。"""

    product_id = add_test_product(db, stock=10)
    response = client.post(
        "/orders/",
        headers=auth_headers,
        json={
            "idempotency_key": "expiration-test-order",
            "address_id": shipping_address_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 2,
                },
            ],
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"], product_id


def test_create_order_and_reduce_stock(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """创建订单后，应保存订单并扣减对应商品库存。"""

    product_id = add_test_product(db_session, stock=10)
    mock_delete = Mock(return_value=1)
    monkeypatch.setattr(redis_client, "delete", mock_delete)

    response = client.post(
        "/orders/",
        headers=auth_headers,
        json={
            "idempotency_key": "create-order-reduce-stock",
            "address_id": shipping_address_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 3,
                },
            ],
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()

    assert response_data["total_amount"] == "897.00"
    assert len(response_data["items"]) == 1

    first_item = response_data["items"][0]
    assert first_item["product_name"] == "测试键盘"
    assert first_item["quantity"] == 3
    assert first_item["product_id"] == product_id
    assert first_item["unit_price"] == "299.00"

    outbox_message = db_session.scalar(
        select(OutboxMessage).where(
            OutboxMessage.order_id == response_data["id"],
        )
    )
    assert outbox_message is not None
    assert outbox_message.event_type == "order.expiration"
    assert outbox_message.payload == {
        "order_id": response_data["id"],
    }
    assert outbox_message.status == OutboxStatus.PENDING

    db_session.expire_all()
    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.stock == 7
    mock_delete.assert_called_once_with(
        f"product:detail:{product_id}"
    )


def test_create_order_is_idempotent_with_same_key(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """相同幂等键和相同请求内容，不应重复创建订单或扣库存。"""

    product_id = add_test_product(
        db_session,
        stock=10,
    )
    payload = {
        "idempotency_key": "same-order-request",
        "address_id": shipping_address_id,
        "items": [
            {
                "product_id": product_id,
                "quantity": 3,
            },
        ],
    }

    first_response = client.post(
        "/orders/",
        headers=auth_headers,
        json=payload,
    )
    second_response = client.post(
        "/orders/",
        headers=auth_headers,
        json=payload,
    )

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_201_CREATED
    assert second_response.json()["id"] == first_response.json()["id"]

    db_session.expire_all()
    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.stock == 7

    outbox_messages = db_session.scalars(
        select(OutboxMessage).where(
            OutboxMessage.order_id
            == first_response.json()["id"],
        )
    ).all()
    assert len(outbox_messages) == 1


def test_create_order_rolls_back_when_outbox_save_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """消息记录保存失败时，订单和库存变化也必须一起回滚。"""

    product_id = add_test_product(
        db_session,
        stock=10,
    )

    def fail_to_add_outbox_message(*_args, **_kwargs) -> None:
        raise SQLAlchemyError("outbox save failed")

    monkeypatch.setattr(
        order_service,
        "add_outbox_message",
        fail_to_add_outbox_message,
    )

    response = client.post(
        "/orders/",
        headers=auth_headers,
        json={
            "idempotency_key": "outbox-save-failure",
            "address_id": shipping_address_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 3,
                },
            ],
        },
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    db_session.expire_all()
    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.stock == 10
    assert db_session.scalar(select(Order)) is None
    assert db_session.scalar(select(OutboxMessage)) is None


def test_create_order_rejects_same_key_with_different_payload(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """相同幂等键不能被不同下单内容复用。"""

    first_product_id = add_test_product(
        db_session,
        stock=10,
        name="第一次幂等商品",
    )
    second_product_id = add_test_product(
        db_session,
        stock=10,
        name="第二次幂等商品",
    )
    first_payload = {
        "idempotency_key": "same-key-different-payload",
        "address_id": shipping_address_id,
        "items": [
            {
                "product_id": first_product_id,
                "quantity": 1,
            },
        ],
    }
    second_payload = {
        "idempotency_key": "same-key-different-payload",
        "address_id": shipping_address_id,
        "items": [
            {
                "product_id": second_product_id,
                "quantity": 1,
            },
        ],
    }

    first_response = client.post(
        "/orders/",
        headers=auth_headers,
        json=first_payload,
    )
    second_response = client.post(
        "/orders/",
        headers=auth_headers,
        json=second_payload,
    )

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_409_CONFLICT
    assert second_response.json() == {
        "detail": "幂等键已被其他订单请求使用",
    }

    db_session.expire_all()
    first_product = db_session.get(
        Product,
        first_product_id,
    )
    second_product = db_session.get(
        Product,
        second_product_id,
    )
    assert first_product is not None
    assert second_product is not None
    assert first_product.stock == 9
    assert second_product.stock == 10


def test_create_order_requires_idempotency_key(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """创建订单必须带幂等键。"""

    product_id = add_test_product(db_session)
    response = client.post(
        "/orders/",
        headers=auth_headers,
        json={
            "address_id": shipping_address_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                },
            ],
        },
    )

    assert response.status_code == (
        status.HTTP_422_UNPROCESSABLE_CONTENT
    )


def test_order_total_amount_is_enforced_by_database(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """即使绕过接口直接改库，订单总金额也不能为负。"""

    order_id = create_test_order(
        client,
        auth_headers,
        shipping_address_id,
        db_session,
    )
    order = db_session.get(Order, order_id)
    assert order is not None

    order.total_amount = Decimal("-1.00")
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_order_status_is_enforced_by_database(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """即使绕过接口直接改库，订单状态也必须在允许范围内。"""

    order_id = create_test_order(
        client,
        auth_headers,
        shipping_address_id,
        db_session,
    )
    order = db_session.get(Order, order_id)
    assert order is not None

    order.status = "unknown"
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_order_item_fields_are_enforced_by_database(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """即使绕过接口直接改库，订单明细数量和单价也不能非法。"""

    order_id = create_test_order(
        client,
        auth_headers,
        shipping_address_id,
        db_session,
    )
    order_item = db_session.scalar(
        select(OrderItem).where(
            OrderItem.order_id == order_id,
        )
    )
    assert order_item is not None

    order_item.quantity = 0
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    order_item = db_session.scalar(
        select(OrderItem).where(
            OrderItem.order_id == order_id,
        )
    )
    assert order_item is not None

    order_item.unit_price = Decimal("-0.01")
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_create_order_with_missing_product(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
) -> None:
    """商品不存在时返回404。"""

    response = client.post(
        "/orders/",
        headers=auth_headers,
        json={
            "idempotency_key": "missing-product",
            "address_id": shipping_address_id,
            "items": [
                {
                    "product_id": 999,
                    "quantity": 1,
                },
            ],
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "商品不存在"}


def test_create_order_with_insufficient_stock(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """库存不足时返回409，并且不改变库存。"""

    product_id = add_test_product(db_session, stock=2)

    response = client.post(
        "/orders/",
        headers=auth_headers,
        json={
            "idempotency_key": "insufficient-stock",
            "address_id": shipping_address_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 3,
                },
            ],
        },
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "商品“测试键盘”库存不足",
    }

    db_session.expire_all()
    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.stock == 2


def test_create_order_without_token(
    client: TestClient,
) -> None:
    response = client.post(
        "/orders/",
        json={
            "idempotency_key": "without-token",
            "address_id": 1,
            "items": [
                {
                    "product_id": 1,
                    "quantity": 1,
                },
            ],
        },
    )

    assert response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )

def test_create_order_with_multiple_products(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    keyboard_id = add_test_product(
        db_session,
        stock=10,
        name="机械键盘",
        price=Decimal("299.00"),
    )

    mouse_id = add_test_product(
        db_session,
        stock=5,
        name="无线鼠标",
        price=Decimal("99.00"),
    )

    response = client.post(
        "/orders/",
        headers=auth_headers,
        json={
            "idempotency_key": "multiple-products",
            "address_id": shipping_address_id,
            "items": [
                {
                    "product_id": keyboard_id,
                    "quantity": 2,
                },
                {
                    "product_id": mouse_id,
                    "quantity": 1,
                },
            ],
        },
    )

    assert response.status_code == status.HTTP_201_CREATED

    response_data = response.json()
    assert response_data["total_amount"] == "697.00"
    assert len(response_data["items"]) == 2

    returned_product_ids = {
        item["product_id"]
        for item in response_data["items"]
    }
    assert returned_product_ids == {
        keyboard_id,
        mouse_id,
    }

    db_session.expire_all()
    keyboard = db_session.get(Product, keyboard_id)
    mouse = db_session.get(Product, mouse_id)

    assert keyboard is not None
    assert mouse is not None
    assert keyboard.stock == 8
    assert mouse.stock == 4


def test_cancel_order_restores_all_product_stock(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    keyboard_id = add_test_product(
        db_session,
        stock=10,
        name="机械键盘",
        price=Decimal("299.00"),
    )
    mouse_id = add_test_product(
        db_session,
        stock=5,
        name="无线鼠标",
        price=Decimal("99.00"),
    )

    create_response = client.post(
        "/orders/",
        headers=auth_headers,
        json={
            "idempotency_key": "cancel-order",
            "address_id": shipping_address_id,
            "items": [
                {
                    "product_id": keyboard_id,
                    "quantity": 2,
                },
                {
                    "product_id": mouse_id,
                    "quantity": 1,
                },
            ],
        },
    )
    assert create_response.status_code == 201
    order_id = create_response.json()["id"]

    cancel_response = client.post(
        f"/orders/{order_id}/cancel",
        headers=auth_headers,
    )

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    db_session.expire_all()
    keyboard = db_session.get(Product, keyboard_id)
    mouse = db_session.get(Product, mouse_id)
    assert keyboard is not None
    assert mouse is not None
    assert keyboard.stock == 10
    assert mouse.stock == 5

    repeated_response = client.post(
        f"/orders/{order_id}/cancel",
        headers=auth_headers,
    )
    assert repeated_response.status_code == 409
    assert repeated_response.json() == {
        "detail": "当前订单状态不允许取消",
    }

    db_session.expire_all()
    assert db_session.get(Product, keyboard_id).stock == 10
    assert db_session.get(Product, mouse_id).stock == 5


def test_expired_pending_order_restores_stock(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """待付款订单过期后，应取消订单并恢复库存。"""

    order_id, product_id = create_expiration_test_order(
        client,
        auth_headers,
        shipping_address_id,
        db_session,
    )
    order = db_session.get(Order, order_id)
    assert order is not None
    order.expires_at = datetime.now() - timedelta(minutes=1)
    db_session.commit()

    expired_order = expire_pending_order(db_session, order_id)

    assert expired_order is not None
    assert expired_order.status == OrderStatus.CANCELLED
    db_session.expire_all()
    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.stock == 10


def test_unexpired_pending_order_keeps_stock(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """尚未过期的待付款订单不应恢复库存。"""

    order_id, product_id = create_expiration_test_order(
        client,
        auth_headers,
        shipping_address_id,
        db_session,
    )

    result = expire_pending_order(db_session, order_id)

    assert result is not None
    assert result.status == OrderStatus.PENDING
    db_session.expire_all()
    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.stock == 8


def test_expired_paid_order_keeps_stock(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """已付款订单即使超过过期时间，也不能取消或恢复库存。"""

    order_id, product_id = create_expiration_test_order(
        client,
        auth_headers,
        shipping_address_id,
        db_session,
    )
    order = db_session.get(Order, order_id)
    assert order is not None
    order.status = OrderStatus.PAID
    order.expires_at = datetime.now() - timedelta(minutes=1)
    db_session.commit()

    result = expire_pending_order(db_session, order_id)

    assert result is not None
    assert result.status == OrderStatus.PAID
    db_session.expire_all()
    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.stock == 8


def test_expire_order_returns_none_when_order_missing(
    db_session: Session,
) -> None:
    """后台任务查询不到订单时，应安全结束。"""

    assert expire_pending_order(db_session, 999_999) is None


def test_expire_order_is_idempotent(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """重复处理同一过期订单时，不能重复增加库存。"""

    order_id, product_id = create_expiration_test_order(
        client,
        auth_headers,
        shipping_address_id,
        db_session,
    )
    order = db_session.get(Order, order_id)
    assert order is not None
    order.expires_at = datetime.now() - timedelta(minutes=1)
    db_session.commit()

    first_result = expire_pending_order(db_session, order_id)
    second_result = expire_pending_order(db_session, order_id)

    assert first_result is not None
    assert second_result is not None
    assert second_result.status == OrderStatus.CANCELLED
    db_session.expire_all()
    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.stock == 10


def test_other_user_cannot_cancel_order(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    product_id = add_test_product(db_session)
    create_response = client.post(
        "/orders/",
        headers=auth_headers,
        json={
            "idempotency_key": "other-user-cannot-cancel",
            "address_id": shipping_address_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                },
            ],
        },
    )
    order_id = create_response.json()["id"]

    register_response = client.post(
        "/auth/register",
        json={
            "name": "其他测试用户",
            "age": 20,
            "username": "other_user",
            "password": "abc123456",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        data={
            "username": "other_user",
            "password": "abc123456",
        },
    )
    other_headers = {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }

    response = client.post(
        f"/orders/{order_id}/cancel",
        headers=other_headers,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "订单不存在或不属于该用户",
    }


def test_cancel_order_without_token(
    client: TestClient,
) -> None:
    response = client.post(
        "/orders/1/cancel",
    )

    assert response.status_code == 401
