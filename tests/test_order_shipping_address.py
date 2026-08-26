from decimal import Decimal

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.order import Order
from app.models.product import Product


def add_shipping_test_product(
    db: Session,
) -> int:
    """创建修改订单地址测试使用的商品。"""

    category = db.scalar(
        select(Category).where(
            Category.name == "订单地址测试分类",
        )
    )
    if category is None:
        category = Category(name="订单地址测试分类")
        db.add(category)
        db.flush()

    product = Product(
        name="订单地址测试商品",
        price=Decimal("60.00"),
        stock=10,
        description="订单地址测试",
        category_id=category.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product.id


def create_shipping_test_order(
    client: TestClient,
    headers: dict[str, str],
    address_id: int,
    product_id: int,
) -> int:
    """创建待付款测试订单。"""

    response = client.post(
        "/orders/",
        headers=headers,
        json={
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
    return response.json()["id"]


def create_second_address(
    client: TestClient,
    headers: dict[str, str],
) -> int:
    """为当前用户创建第二条收货地址。"""

    response = client.post(
        "/addresses/",
        headers=headers,
        json={
            "receiver_name": "新的收货人",
            "phone": "13900139000",
            "province": "浙江省",
            "city": "杭州市",
            "district": "西湖区",
            "detail_address": "文三路2号",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_pending_order_can_change_shipping_address(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """待付款订单可以复制当前用户的新地址快照。"""

    product_id = add_shipping_test_product(db_session)
    order_id = create_shipping_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    new_address_id = create_second_address(
        client,
        auth_headers,
    )

    response = client.patch(
        f"/orders/{order_id}/shipping-address",
        headers=auth_headers,
        json={"address_id": new_address_id},
    )

    assert response.status_code == 200
    assert response.json()["receiver_name"] == "新的收货人"
    assert response.json()["phone"] == "13900139000"
    assert response.json()["province"] == "浙江省"
    assert response.json()["city"] == "杭州市"
    assert response.json()["district"] == "西湖区"
    assert response.json()["detail_address"] == "文三路2号"


def test_paid_order_cannot_change_shipping_address(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """订单离开待付款状态后不允许修改地址。"""

    product_id = add_shipping_test_product(db_session)
    order_id = create_shipping_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    new_address_id = create_second_address(
        client,
        auth_headers,
    )

    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order is not None
    order.status = "paid"
    db_session.commit()

    response = client.patch(
        f"/orders/{order_id}/shipping-address",
        headers=auth_headers,
        json={"address_id": new_address_id},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "只有待付款订单可以修改收货地址",
    }


def test_order_rejects_another_users_address(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """不能把其他用户的地址复制到自己的订单。"""

    product_id = add_shipping_test_product(db_session)
    order_id = create_shipping_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )

    register_response = client.post(
        "/auth/register",
        json={
            "name": "其他地址用户",
            "age": 20,
            "username": "other_shipping_user",
            "password": "abc123456",
        },
    )
    assert register_response.status_code == 201
    login_response = client.post(
        "/auth/login",
        data={
            "username": "other_shipping_user",
            "password": "abc123456",
        },
    )
    other_headers = {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }
    other_address_id = create_second_address(
        client,
        other_headers,
    )

    response = client.patch(
        f"/orders/{order_id}/shipping-address",
        headers=auth_headers,
        json={"address_id": other_address_id},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "收货地址不存在",
    }
