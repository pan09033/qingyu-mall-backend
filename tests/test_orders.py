from decimal import Decimal

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product


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


def test_create_order_and_reduce_stock(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """创建订单后，应保存订单并扣减对应商品库存。"""

    product_id = add_test_product(db_session, stock=10)

    response = client.post(
        "/orders/",
        headers=auth_headers,
        json={
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

    db_session.expire_all()
    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.stock == 7


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
