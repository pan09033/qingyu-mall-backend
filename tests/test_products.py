from fastapi import status
from fastapi.testclient import TestClient


def test_get_product_and_missing_product(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """商品详情存在时返回商品，不存在时返回统一的404。"""

    category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "商品详情测试分类"},
    ).json()
    product = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "商品详情测试商品",
            "price": 99,
            "stock": 5,
            "category_id": category["id"],
        },
    ).json()

    found_response = client.get(
        f"/products/{product['id']}",
    )
    assert found_response.status_code == status.HTTP_200_OK
    assert found_response.json()["id"] == product["id"]

    missing_response = client.get(
        "/products/999",
    )
    assert missing_response.status_code == status.HTTP_404_NOT_FOUND
    assert missing_response.json() == {
        "detail": "商品不存在",
    }


def test_admin_can_delete_unused_product(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """管理员可以删除没有历史订单的商品。"""

    category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "删除商品测试分类"},
    ).json()
    product = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "待删除商品",
            "price": 50,
            "stock": 5,
            "category_id": category["id"],
        },
    ).json()

    response = client.delete(
        f"/products/{product['id']}",
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    get_response = client.get(
        f"/products/{product['id']}",
    )
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


def test_regular_user_cannot_delete_product(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """普通用户不能调用管理员删除商品接口。"""

    response = client.delete(
        "/products/999",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_cannot_delete_product_used_by_order(
    client: TestClient,
    admin_headers: dict[str, str],
    shipping_address_id: int,
) -> None:
    """已有历史订单明细的商品不能物理删除。"""

    category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "订单商品删除保护分类"},
    ).json()
    product = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "已有订单商品",
            "price": 60,
            "stock": 10,
            "category_id": category["id"],
        },
    ).json()
    order_response = client.post(
        "/orders/",
        headers=admin_headers,
        json={
            "address_id": shipping_address_id,
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": 1,
                },
            ],
        },
    )
    assert order_response.status_code == status.HTTP_201_CREATED

    response = client.delete(
        f"/products/{product['id']}",
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "商品已有业务记录，不能删除",
    }


def test_create_product_with_existing_category(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    category_response = client.post(
        "/categories/",
        headers=admin_headers,
        json={
            "name": "键盘分类",
        },
    )
    assert category_response.status_code == (
        status.HTTP_201_CREATED
    )
    category_id = category_response.json()["id"]

    response = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "机械键盘",
            "price": 299,
            "stock": 20,
            "description": "青轴机械键盘",
            "category_id": category_id,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["category_id"] == category_id


def test_create_product_with_missing_category(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    response = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "机械键盘",
            "price": 299,
            "stock": 20,
            "category_id": 999,
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "商品分类不存在",
    }


def test_update_product_category_success(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    first_category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "原分类"},
    ).json()
    second_category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "新分类"},
    ).json()

    product_response = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "机械键盘",
            "price": 299,
            "stock": 20,
            "category_id": first_category["id"],
        },
    )
    assert product_response.status_code == (
        status.HTTP_201_CREATED
    )
    product_id = product_response.json()["id"]

    response = client.patch(
        f"/products/{product_id}",
        headers=admin_headers,
        json={
            "category_id": second_category["id"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["category_id"] == (
        second_category["id"]
    )


def test_update_product_with_missing_category(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    category_response = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "原分类"},
    )
    category_id = category_response.json()["id"]

    product_response = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "机械键盘",
            "price": 299,
            "stock": 20,
            "category_id": category_id,
        },
    )
    product_id = product_response.json()["id"]

    response = client.patch(
        f"/products/{product_id}",
        headers=admin_headers,
        json={"category_id": 999},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "商品分类不存在",
    }

    get_response = client.get(
        f"/products/{product_id}",
    )
    assert get_response.json()["category_id"] == category_id


def test_filter_products_by_category_and_keyword(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    keyboard_category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "键盘"},
    ).json()
    mouse_category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "鼠标"},
    ).json()

    product_inputs = [
        ("机械键盘", keyboard_category["id"]),
        ("薄膜键盘", keyboard_category["id"]),
        ("无线鼠标", mouse_category["id"]),
    ]
    for name, category_id in product_inputs:
        response = client.post(
            "/products/",
            headers=admin_headers,
            json={
                "name": name,
                "price": 100,
                "stock": 10,
                "category_id": category_id,
            },
        )
        assert response.status_code == 201

    category_response = client.get(
        "/products/",
        params={
            "category_id": keyboard_category["id"],
        },
    )
    assert category_response.status_code == 200
    assert category_response.json()["total"] == 2

    combined_response = client.get(
        "/products/",
        params={
            "category_id": keyboard_category["id"],
            "keyword": "机械",
        },
    )
    assert combined_response.json()["total"] == 1
    assert combined_response.json()["items"][0]["name"] == (
        "机械键盘"
    )

    empty_response = client.get(
        "/products/",
        params={"category_id": 999},
    )
    assert empty_response.status_code == 200
    assert empty_response.json()["items"] == []
    assert empty_response.json()["total"] == 0

    paginated_response = client.get(
        "/products/",
        params={
            "category_id": keyboard_category["id"],
            "skip": 1,
            "limit": 1,
        },
    )
    assert len(paginated_response.json()["items"]) == 1
    assert paginated_response.json()["total"] == 2
