from decimal import Decimal

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.cart_item import CartItem
from app.models.product import Product


def add_cart_test_product(
    db: Session,
    name: str = "购物车测试商品",
    price: Decimal = Decimal("100.00"),
    stock: int = 10,
) -> int:
    """直接创建购物车测试使用的商品。"""

    category = db.scalar(
        select(Category).where(
            Category.name == "购物车测试分类",
        )
    )
    if category is None:
        category = Category(
            name="购物车测试分类",
        )
        db.add(category)
        db.flush()

    product = Product(
        name=name,
        price=price,
        stock=stock,
        description="购物车测试",
        category_id=category.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product.id


def login_second_cart_user(
    client: TestClient,
) -> dict[str, str]:
    """创建并登录第二个购物车测试用户。"""

    register_response = client.post(
        "/auth/register",
        json={
            "name": "其他购物车用户",
            "age": 20,
            "username": "other_cart_user",
            "password": "abc123456",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        data={
            "username": "other_cart_user",
            "password": "abc123456",
        },
    )
    assert login_response.status_code == 200
    return {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }


def test_add_product_and_get_cart_totals(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """购物车应返回当前价格、小计、总数量和总金额。"""

    product_id = add_cart_test_product(
        db_session,
        price=Decimal("99.00"),
    )
    add_response = client.post(
        "/cart/items",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "quantity": 2,
        },
    )

    assert add_response.status_code == status.HTTP_201_CREATED
    assert add_response.json()["subtotal"] == "198.00"

    response = client.get(
        "/cart/",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["total_quantity"] == 2
    assert response.json()["total_amount"] == "198.00"
    assert len(response.json()["items"]) == 1


def test_adding_same_product_merges_quantity(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """同一商品重复加入时，只保留一条记录并累加数量。"""

    product_id = add_cart_test_product(db_session)
    for quantity in (2, 3):
        response = client.post(
            "/cart/items",
            headers=auth_headers,
            json={
                "product_id": product_id,
                "quantity": quantity,
            },
        )
        assert response.status_code == 201

    response = client.get(
        "/cart/",
        headers=auth_headers,
    )
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["quantity"] == 5
    assert response.json()["total_quantity"] == 5


def test_cart_rejects_accumulated_quantity_above_99(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """单次加入合法，但累计超过99件时拒绝并保留原数量。"""

    product_id = add_cart_test_product(
        db_session,
        stock=200,
    )
    first_response = client.post(
        "/cart/items",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "quantity": 60,
        },
    )
    second_response = client.post(
        "/cart/items",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "quantity": 60,
        },
    )

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_409_CONFLICT
    assert second_response.json() == {
        "detail": "同一商品最多加入购物车99件",
    }

    cart_response = client.get(
        "/cart/",
        headers=auth_headers,
    )
    assert cart_response.json()["items"][0]["quantity"] == 60


def test_cart_item_quantity_range_is_enforced_by_database(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """即使绕过接口直接改库，购物车数量也不能超过99。"""

    product_id = add_cart_test_product(
        db_session,
        stock=200,
    )
    response = client.post(
        "/cart/items",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "quantity": 1,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    cart_item = db_session.scalar(
        select(CartItem).where(
            CartItem.product_id == product_id,
        )
    )
    assert cart_item is not None

    cart_item.quantity = 100
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_cart_rejects_quantity_above_current_stock(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """加入数量超过当前库存时返回409，购物车保持为空。"""

    product_id = add_cart_test_product(
        db_session,
        stock=2,
    )
    response = client.post(
        "/cart/items",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "quantity": 3,
        },
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "商品“购物车测试商品”库存不足",
    }

    cart_response = client.get(
        "/cart/",
        headers=auth_headers,
    )
    assert cart_response.json()["items"] == []


def test_update_delete_and_clear_cart(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """用户可以修改数量、删除单项并清空购物车。"""

    first_product_id = add_cart_test_product(
        db_session,
        name="购物车商品A",
    )
    second_product_id = add_cart_test_product(
        db_session,
        name="购物车商品B",
    )

    first_item = client.post(
        "/cart/items",
        headers=auth_headers,
        json={
            "product_id": first_product_id,
            "quantity": 1,
        },
    ).json()
    client.post(
        "/cart/items",
        headers=auth_headers,
        json={
            "product_id": second_product_id,
            "quantity": 1,
        },
    )

    update_response = client.patch(
        f"/cart/items/{first_item['id']}",
        headers=auth_headers,
        json={"quantity": 4},
    )
    assert update_response.status_code == 200
    assert update_response.json()["quantity"] == 4

    delete_response = client.delete(
        f"/cart/items/{first_item['id']}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204

    clear_response = client.delete(
        "/cart/",
        headers=auth_headers,
    )
    assert clear_response.status_code == 204

    cart_response = client.get(
        "/cart/",
        headers=auth_headers,
    )
    assert cart_response.json()["items"] == []
    assert cart_response.json()["total_amount"] == "0.00"


def test_user_cannot_modify_other_users_cart_item(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """购物车记录ID存在，但不属于当前用户时返回404。"""

    product_id = add_cart_test_product(db_session)
    cart_item_id = client.post(
        "/cart/items",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "quantity": 1,
        },
    ).json()["id"]
    other_headers = login_second_cart_user(client)

    response = client.patch(
        f"/cart/items/{cart_item_id}",
        headers=other_headers,
        json={"quantity": 2},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "购物车商品不存在",
    }
