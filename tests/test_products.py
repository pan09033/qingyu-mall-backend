from unittest.mock import Mock, call

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import product_cache
from app.models.product import Product
from app.redis_client import redis_client
from app.schemas.product import ProductCreate, ProductResponse
from app.services import product as product_service


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
            "idempotency_key": "product-delete-protection",
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


def test_create_and_update_product_image(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """管理员可以设置、修改并清除商品主图地址。"""

    category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "商品图片分类"},
    ).json()
    image_url = "https://example.com/product.jpg"
    product = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "带主图商品",
            "price": 199,
            "stock": 8,
            "category_id": category["id"],
            "image_url": image_url,
        },
    ).json()

    assert product["image_url"] == image_url

    clear_response = client.patch(
        f"/products/{product['id']}",
        headers=admin_headers,
        json={"image_url": None},
    )
    assert clear_response.status_code == status.HTTP_200_OK
    assert clear_response.json()["image_url"] is None


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
        ("机械键盘", keyboard_category["id"], "青轴手感"),
        ("薄膜键盘", keyboard_category["id"], "轻薄键盘"),
        ("无线鼠标", mouse_category["id"], "适合静音办公"),
    ]
    for name, category_id, description in product_inputs:
        response = client.post(
            "/products/",
            headers=admin_headers,
            json={
                "name": name,
                "price": 100,
                "stock": 10,
                "description": description,
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

    description_response = client.get(
        "/products/",
        params={"keyword": "静音办公"},
    )
    assert description_response.status_code == 200
    assert description_response.json()["total"] == 1
    assert description_response.json()["items"][0]["name"] == (
        "无线鼠标"
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


def test_get_product_uses_redis_cache(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis 命中时直接返回缓存商品。"""

    cached_product = ProductResponse(
        id=999,
        name="Redis缓存商品",
        price=88,
        stock=5,
        description=None,
        image_url=None,
        category_id=1,
    ).model_dump_json()

    monkeypatch.setattr(
        redis_client,
        "get",
        lambda _key: cached_product,
    )

    response = client.get(
        "/products/999",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "Redis缓存商品"


def test_product_cache_miss_writes_redis(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis 未命中时查询 MySQL，并写入带 TTL 的缓存。"""

    category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "缓存未命中测试分类"},
    ).json()
    product = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "缓存未命中测试商品",
            "price": 66,
            "stock": 6,
            "category_id": category["id"],
        },
    ).json()

    mock_get = Mock(return_value=None)
    mock_set = Mock(return_value=True)
    monkeypatch.setattr(
        redis_client,
        "get",
        mock_get,
    )
    monkeypatch.setattr(
        redis_client,
        "set",
        mock_set,
    )

    response = client.get(
        f"/products/{product['id']}",
    )

    assert response.status_code == status.HTTP_200_OK

    cache_key = f"product:detail:{product['id']}"
    assert mock_get.call_args_list == [call(cache_key), call(cache_key)]
    assert mock_set.call_count == 2
    lock_call = mock_set.call_args_list[0]
    assert lock_call.args[0] == f"lock:product:detail:{product['id']}"
    assert lock_call.kwargs == {"nx": True, "ex": 5}

    set_args = mock_set.call_args.args
    set_kwargs = mock_set.call_args.kwargs
    cached_product = ProductResponse.model_validate_json(
        set_args[1]
    )

    assert set_args[0] == cache_key
    assert set(set_kwargs) == {"ex"}
    assert 300 <= set_kwargs["ex"] <= 360
    assert cached_product.id == product["id"]
    assert cached_product.name == product["name"]


def test_product_cache_generates_ttl_for_each_write(monkeypatch):
    """控制随机值覆盖上下界，确认每次写入都重新计算TTL。"""
    random_offset = Mock(side_effect=[0, 60, 23])
    write = Mock(return_value=True)
    monkeypatch.setattr(product_cache.random, "randint", random_offset)
    monkeypatch.setattr(redis_client, "set", write)
    product = ProductResponse(
        id=2, name="随机TTL商品", price=99, stock=5, category_id=1,
    )

    for _ in range(3):
        product_cache.cache_product(product)

    assert [item.kwargs["ex"] for item in write.call_args_list] == [300, 360, 323]
    assert random_offset.call_args_list == [call(0, 60)] * 3


def test_invalid_product_cache_falls_back_to_database(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """损坏的缓存不能让商品详情接口返回 500。"""

    category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "损坏缓存测试分类"},
    ).json()
    product = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "损坏缓存测试商品",
            "price": 66,
            "stock": 6,
            "category_id": category["id"],
        },
    ).json()

    mock_delete = Mock(return_value=1)
    monkeypatch.setattr(
        redis_client,
        "get",
        Mock(side_effect=["not-valid-json", None]),
    )
    monkeypatch.setattr(redis_client, "delete", mock_delete)

    response = client.get(f"/products/{product['id']}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == product["id"]
    mock_delete.assert_called_once_with(
        f"product:detail:{product['id']}"
    )


def test_missing_product_writes_short_lived_negative_cache(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MySQL 确认商品不存在后，写入 60 秒的空值缓存。"""

    mock_get = Mock(return_value=None)
    mock_set = Mock(return_value=True)
    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(redis_client, "set", mock_set)

    response = client.get("/products/999999")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert mock_get.call_args_list == [
        call("product:detail:999999"),
        call("product:detail:999999"),
    ]
    assert mock_set.call_count == 2
    mock_set.assert_called_with(
        "product:detail:999999",
        "__product_not_found__",
        ex=60,
    )


def test_negative_cache_hit_skips_database(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """空值缓存命中时直接返回 404，不重复查询 MySQL。"""

    mock_database_get = Mock(return_value=None)
    monkeypatch.setattr(
        redis_client,
        "get",
        Mock(return_value="__product_not_found__"),
    )
    monkeypatch.setattr(
        product_service,
        "get_product_by_id",
        mock_database_get,
    )

    response = client.get("/products/999999")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "商品不存在"}
    mock_database_get.assert_not_called()


def test_create_product_clears_possible_negative_cache(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """创建商品后删除同 ID 的旧空值缓存。"""

    category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "创建商品清理空值缓存分类"},
    ).json()
    mock_delete = Mock(return_value=1)
    monkeypatch.setattr(redis_client, "delete", mock_delete)

    response = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "创建商品清理空值缓存商品",
            "price": 100,
            "stock": 10,
            "category_id": category["id"],
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    product_id = response.json()["id"]
    mock_delete.assert_called_once_with(
        f"product:detail:{product_id}"
    )


def test_update_product_deletes_redis_cache(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """商品更新成功后删除对应的 Redis 缓存。"""

    category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "更新缓存失效测试分类"},
    ).json()
    product = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "更新缓存失效测试商品",
            "price": 100,
            "stock": 10,
            "category_id": category["id"],
        },
    ).json()

    mock_delete = Mock(return_value=1)
    monkeypatch.setattr(
        redis_client,
        "delete",
        mock_delete,
    )

    response = client.patch(
        f"/products/{product['id']}",
        headers=admin_headers,
        json={"price": 200},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["price"] == 200

    cache_key = f"product:detail:{product['id']}"
    mock_delete.assert_called_once_with(
        cache_key
    )


def test_product_create_strips_name() -> None:
    """创建商品时自动清理名称两端的空格。"""

    product = ProductCreate(
        name="  机械键盘  ",
        price="299.00",
        stock=10,
        category_id=1,
    )

    assert product.name == "机械键盘"


@pytest.mark.parametrize(
    "invalid_name",
    [
        "   ",
        "a" * 31,
    ],
)
def test_product_create_rejects_invalid_name(
    invalid_name: str,
) -> None:
    """创建商品时拒绝纯空格和超过30个字符的名称。"""

    with pytest.raises(ValidationError):
        ProductCreate(
            name=invalid_name,
            price="299.00",
            stock=10,
            category_id=1,
        )


def test_database_rejects_negative_product_stock(
    db_session: Session,
) -> None:
    """绕过 Pydantic 写入时，数据库仍拒绝负库存。"""

    db_session.add(
        Product(
            name="负库存商品",
            price="99.00",
            stock=-1,
            category_id=1,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()
