from decimal import Decimal
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product
from app.config import settings


def add_status_test_product(
    db: Session,
    stock: int = 5,
) -> int:
    """创建订单状态测试商品。"""

    category = db.scalar(
        select(Category).where(
            Category.name == "订单状态测试分类",
        )
    )
    if category is None:
        category = Category(
            name="订单状态测试分类",
        )
        db.add(category)
        db.flush()

    product = Product(
        name="订单状态测试商品",
        price=Decimal("50.00"),
        stock=stock,
        description="状态测试",
        category_id=category.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product.id


def create_pending_order(
    client: TestClient,
    headers: dict[str, str],
    address_id: int,
    product_id: int,
) -> int:
    """创建一条待付款订单并返回订单ID。"""

    response = client.post(
        "/orders/",
        headers=headers,
        json={
            "idempotency_key": f"status-order-{uuid4().hex}",
            "address_id": address_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                },
            ],
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    return response.json()["id"]


def login_other_status_user(
    client: TestClient,
) -> dict[str, str]:
    """创建并登录另一名普通用户。"""

    response = client.post(
        "/auth/register",
        json={
            "name": "状态测试其他用户",
            "age": 20,
            "username": "other_status_user",
            "password": "abc123456",
        },
    )
    assert response.status_code == 201

    response = client.post(
        "/auth/login",
        data={
            "username": "other_status_user",
            "password": "abc123456",
        },
    )
    assert response.status_code == 200
    return {
        "Authorization": (
            f"Bearer {response.json()['access_token']}"
        ),
    }


def pay_order_through_callback(
    client: TestClient,
    headers: dict[str, str],
    order_id: int,
) -> None:
    """通过支付记录和模拟平台回调完成订单支付。"""

    payment_response = client.post(
        f"/payments/orders/{order_id}",
        headers=headers,
    )
    assert payment_response.status_code == 201
    payment = payment_response.json()

    callback_response = client.post(
        "/payments/callback",
        headers={
            "X-Payment-Secret": (
                settings.payment_callback_secret
            ),
        },
        json={
            "payment_id": payment["id"],
            "transaction_no": f"TEST-{order_id}",
            "amount": payment["amount"],
        },
    )
    assert callback_response.status_code == 200
    assert callback_response.json()["status"] == "success"


def test_order_follows_complete_status_flow(
    client: TestClient,
    admin_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """订单应按待付款、已付款、已发货、已完成依次流转。"""

    product_id = add_status_test_product(db_session)
    order_id = create_pending_order(
        client,
        admin_headers,
        shipping_address_id,
        product_id,
    )

    pay_order_through_callback(
        client,
        admin_headers,
        order_id,
    )

    ship_response = client.post(
        f"/orders/{order_id}/ship",
        headers=admin_headers,
    )
    assert ship_response.status_code == 200
    assert ship_response.json()["status"] == "shipped"

    complete_response = client.post(
        f"/orders/{order_id}/complete",
        headers=admin_headers,
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"

    cancel_response = client.post(
        f"/orders/{order_id}/cancel",
        headers=admin_headers,
    )
    assert cancel_response.status_code == 409

    db_session.expire_all()
    assert db_session.get(Product, product_id).stock == 4


def test_regular_user_cannot_ship_order(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """发货接口只允许管理员调用。"""

    product_id = add_status_test_product(db_session)
    order_id = create_pending_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )

    response = client.post(
        f"/orders/{order_id}/ship",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_pending_order_cannot_be_shipped_directly(
    client: TestClient,
    admin_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """管理员也不能跳过付款状态直接发货。"""

    product_id = add_status_test_product(db_session)
    order_id = create_pending_order(
        client,
        admin_headers,
        shipping_address_id,
        product_id,
    )

    response = client.post(
        f"/orders/{order_id}/ship",
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "只有已付款订单可以发货",
    }


def test_user_cannot_pay_other_users_order(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """普通用户不能通过猜测订单ID支付其他用户的订单。"""

    product_id = add_status_test_product(db_session)
    order_id = create_pending_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    other_headers = login_other_status_user(client)

    response = client.post(
        f"/payments/orders/{order_id}",
        headers=other_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "订单不存在或不属于该用户",
    }
