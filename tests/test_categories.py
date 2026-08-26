from fastapi.testclient import TestClient


def test_update_category_success(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    create_response = client.post(
        "/categories/",
        headers=admin_headers,
        json={
            "name": "键盘",
            "description": "键盘类商品",
        },
    )
    assert create_response.status_code == 201
    category_id = create_response.json()["id"]

    update_response = client.patch(
        f"/categories/{category_id}",
        headers=admin_headers,
        json={
            "name": "机械键盘",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "机械键盘"
    assert (
        update_response.json()["description"]
        == "键盘类商品"
    )


def test_update_category_rejects_duplicate_name(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    first_response = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "键盘"},
    )
    second_response = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "鼠标"},
    )
    assert first_response.status_code == 201
    assert second_response.status_code == 201

    category_id = second_response.json()["id"]
    response = client.patch(
        f"/categories/{category_id}",
        headers=admin_headers,
        json={"name": "键盘"},
    )

    assert response.status_code == 409


def test_update_missing_category_returns_404(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    response = client.patch(
        "/categories/999",
        headers=admin_headers,
        json={"name": "不存在的分类"},
    )

    assert response.status_code == 404


def test_normal_user_cannot_update_category(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.patch(
        "/categories/1",
        headers=auth_headers,
        json={"name": "键盘"},
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_update_category(
    client: TestClient,
) -> None:
    response = client.patch(
        "/categories/1",
        json={"name": "键盘"},
    )

    assert response.status_code == 401


def test_delete_category_success(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    create_response = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "待删除分类"},
    )
    assert create_response.status_code == 201
    category_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/categories/{category_id}",
        headers=admin_headers,
    )
    assert delete_response.status_code == 204
    assert delete_response.content == b""

    get_response = client.get(
        f"/categories/{category_id}",
    )
    assert get_response.status_code == 404


def test_delete_missing_category_returns_404(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    response = client.delete(
        "/categories/999",
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_normal_user_cannot_delete_category(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.delete(
        "/categories/1",
        headers=auth_headers,
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_delete_category(
    client: TestClient,
) -> None:
    response = client.delete(
        "/categories/1",
    )

    assert response.status_code == 401


def test_category_with_products_cannot_be_deleted(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    category_response = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "键盘分类"},
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
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]

    delete_response = client.delete(
        f"/categories/{category_id}",
        headers=admin_headers,
    )

    assert delete_response.status_code == 409
    assert delete_response.json() == {
        "detail": "该分类下存在商品，不能删除",
    }

    assert client.get(
        f"/categories/{category_id}",
    ).status_code == 200
    assert client.get(
        f"/products/{product_id}",
    ).status_code == 200
