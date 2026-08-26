from decimal import Decimal

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.order import Order
from app.models.product import Product


def add_admin_order_test_product(
    db: Session,
) -> int:
    """创建管理员订单查询测试商品。"""

    category = db.scalar(
        select(Category).where(
            Category.name == "管理员订单测试分类",
        )
    )
    if category is None:
        category = Category(
            name="管理员订单测试分类",
        )
        db.add(category)
        db.flush()

    product = Product(
        name="管理员订单测试商品",
        price=Decimal("30.00"),
        stock=20,
        description="管理员订单测试",
        category_id=category.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product.id


def create_order_for_admin_test(
    client: TestClient,
    headers: dict[str, str],
    address_id: int,
    product_id: int,
) -> int:
    """创建一条管理员查询测试订单。"""

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


def create_other_user_with_address(
    client: TestClient,
) -> tuple[int, dict[str, str], int]:
    """创建另一名用户，并返回用户ID、请求头和地址ID。"""

    register_response = client.post(
        "/auth/register",
        json={
            "name": "订单筛选用户",
            "age": 20,
            "username": "admin_order_other_user",
            "password": "abc123456",
        },
    )
    assert register_response.status_code == 201
    user_id = register_response.json()["id"]

    login_response = client.post(
        "/auth/login",
        data={
            "username": "admin_order_other_user",
            "password": "abc123456",
        },
    )
    headers = {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }

    address_response = client.post(
        "/addresses/",
        headers=headers,
        json={
            "receiver_name": "订单筛选用户",
            "phone": "13700137000",
            "province": "江苏省",
            "city": "南京市",
            "district": "玄武区",
            "detail_address": "测试路1号",
        },
    )
    assert address_response.status_code == 201
    return user_id, headers, address_response.json()["id"]


def test_admin_can_filter_and_paginate_orders(
    client: TestClient,
    admin_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """管理员可以按用户、状态筛选，并正确获得分页总数。"""

    product_id = add_admin_order_test_product(db_session)
    first_order_id = create_order_for_admin_test(
        client,
        admin_headers,
        shipping_address_id,
        product_id,
    )
    second_order_id = create_order_for_admin_test(
        client,
        admin_headers,
        shipping_address_id,
        product_id,
    )

    db_session.expire_all()
    first_order = db_session.get(Order, first_order_id)
    assert first_order is not None
    first_order.status = "paid"
    db_session.commit()

    other_user_id, other_headers, other_address_id = (
        create_other_user_with_address(client)
    )
    other_order_id = create_order_for_admin_test(
        client,
        other_headers,
        other_address_id,
        product_id,
    )

    all_response = client.get(
        "/admin/orders",
        headers=admin_headers,
    )
    assert all_response.status_code == 200
    assert all_response.json()["total"] == 3
    assert [
        item["id"]
        for item in all_response.json()["items"]
    ] == [
        other_order_id,
        second_order_id,
        first_order_id,
    ]

    status_response = client.get(
        "/admin/orders",
        headers=admin_headers,
        params={"status": "pending"},
    )
    assert status_response.json()["total"] == 2

    user_response = client.get(
        "/admin/orders",
        headers=admin_headers,
        params={"user_id": other_user_id},
    )
    assert user_response.json()["total"] == 1
    assert user_response.json()["items"][0]["id"] == other_order_id

    combined_response = client.get(
        "/admin/orders",
        headers=admin_headers,
        params={
            "user_id": other_user_id,
            "status": "paid",
        },
    )
    assert combined_response.json()["total"] == 0

    page_response = client.get(
        "/admin/orders",
        headers=admin_headers,
        params={
            "skip": 1,
            "limit": 1,
        },
    )
    assert page_response.json()["total"] == 3
    assert len(page_response.json()["items"]) == 1


def test_regular_user_cannot_list_admin_orders(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """普通用户不能访问管理员订单列表。"""

    response = client.get(
        "/admin/orders",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
