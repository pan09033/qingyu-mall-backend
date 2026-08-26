from decimal import Decimal

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.order import Order
from app.models.product import Product


def add_refund_test_product(
    db: Session,
) -> int:
    """创建退款申请测试商品。"""

    category = db.scalar(
        select(Category).where(
            Category.name == "退款测试分类",
        )
    )
    if category is None:
        category = Category(name="退款测试分类")
        db.add(category)
        db.flush()

    product = Product(
        name="退款测试商品",
        price=Decimal("70.00"),
        stock=10,
        description="退款测试",
        category_id=category.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product.id


def create_refund_test_order(
    client: TestClient,
    headers: dict[str, str],
    address_id: int,
    product_id: int,
) -> int:
    """创建退款测试订单。"""

    response = client.post(
        "/orders/",
        headers=headers,
        json={
            "address_id": address_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 2,
                },
            ],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_paid_order_can_create_refund_request(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """已付款未发货订单可以创建退款申请并改变订单状态。"""

    product_id = add_refund_test_product(db_session)
    order_id = create_refund_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    order = db_session.get(Order, order_id)
    assert order is not None
    order.status = "paid"
    db_session.commit()

    response = client.post(
        f"/refunds/orders/{order_id}",
        headers=auth_headers,
        json={
            "reason": "  不再需要该商品  ",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["order_id"] == order_id
    assert response.json()["amount"] == "140.00"
    assert response.json()["reason"] == "不再需要该商品"
    assert response.json()["status"] == "pending"

    db_session.expire_all()
    assert db_session.get(Order, order_id).status == "refund_pending"


def test_pending_order_cannot_create_refund_request(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """尚未付款的订单不能申请退款。"""

    product_id = add_refund_test_product(db_session)
    order_id = create_refund_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )

    response = client.post(
        f"/refunds/orders/{order_id}",
        headers=auth_headers,
        json={"reason": "不再需要"},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "只有已付款未发货订单可以申请退款",
    }


def test_user_cannot_refund_other_users_order(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """用户不能为其他用户的订单申请退款。"""

    product_id = add_refund_test_product(db_session)
    order_id = create_refund_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    order = db_session.get(Order, order_id)
    assert order is not None
    order.status = "paid"
    db_session.commit()

    register_response = client.post(
        "/auth/register",
        json={
            "name": "其他退款用户",
            "age": 20,
            "username": "other_refund_user",
            "password": "abc123456",
        },
    )
    assert register_response.status_code == 201
    login_response = client.post(
        "/auth/login",
        data={
            "username": "other_refund_user",
            "password": "abc123456",
        },
    )
    other_headers = {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }

    response = client.post(
        f"/refunds/orders/{order_id}",
        headers=other_headers,
        json={"reason": "尝试退款"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
