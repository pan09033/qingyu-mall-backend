from fastapi import status
from fastapi.testclient import TestClient


def address_body(
    receiver_name: str,
    detail_address: str,
    is_default: bool = False,
) -> dict:
    """生成测试使用的地址请求体。"""

    return {
        "receiver_name": receiver_name,
        "phone": "13800138000",
        "province": "广东省",
        "city": "深圳市",
        "district": "南山区",
        "detail_address": detail_address,
        "is_default": is_default,
    }


def register_other_user(
    client: TestClient,
) -> dict[str, str]:
    """注册并登录第二个测试用户。"""

    register_response = client.post(
        "/auth/register",
        json={
            "name": "其他用户",
            "age": 20,
            "username": "address_other_user",
            "password": "abc123456",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        data={
            "username": "address_other_user",
            "password": "abc123456",
        },
    )
    assert login_response.status_code == 200

    return {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }


def test_first_address_becomes_default(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """用户创建的第一条地址应自动成为默认地址。"""

    response = client.post(
        "/addresses/",
        headers=auth_headers,
        json=address_body(
            "小明",
            "科技园1号",
        ),
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["receiver_name"] == "小明"
    assert response.json()["is_default"] is True


def test_new_default_address_replaces_old_default(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """创建新的默认地址时，应取消旧地址的默认状态。"""

    first_response = client.post(
        "/addresses/",
        headers=auth_headers,
        json=address_body(
            "小明",
            "科技园1号",
        ),
    )
    second_response = client.post(
        "/addresses/",
        headers=auth_headers,
        json=address_body(
            "小明",
            "科技园2号",
            is_default=True,
        ),
    )
    assert first_response.status_code == 201
    assert second_response.status_code == 201

    list_response = client.get(
        "/addresses/",
        headers=auth_headers,
    )
    addresses = list_response.json()

    assert list_response.status_code == 200
    assert len(addresses) == 2
    assert addresses[0]["id"] == second_response.json()["id"]
    assert addresses[0]["is_default"] is True
    assert addresses[1]["is_default"] is False


def test_non_default_addresses_are_sorted_newest_first(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """默认地址优先，其他地址按照最新创建的在前排列。"""

    first_id = client.post(
        "/addresses/",
        headers=auth_headers,
        json=address_body("小明", "科技园1号"),
    ).json()["id"]
    second_id = client.post(
        "/addresses/",
        headers=auth_headers,
        json=address_body("小明", "科技园2号"),
    ).json()["id"]
    third_id = client.post(
        "/addresses/",
        headers=auth_headers,
        json=address_body("小明", "科技园3号"),
    ).json()["id"]

    response = client.get(
        "/addresses/",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert [
        address["id"]
        for address in response.json()
    ] == [
        first_id,
        third_id,
        second_id,
    ]


def test_update_and_set_default_address(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """用户可以修改自己的地址，并切换默认地址。"""

    first_id = client.post(
        "/addresses/",
        headers=auth_headers,
        json=address_body("小明", "科技园1号"),
    ).json()["id"]
    second_id = client.post(
        "/addresses/",
        headers=auth_headers,
        json=address_body("小明", "科技园2号"),
    ).json()["id"]

    update_response = client.patch(
        f"/addresses/{second_id}",
        headers=auth_headers,
        json={
            "receiver_name": "小红",
            "detail_address": "科技园3号",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["receiver_name"] == "小红"
    assert update_response.json()["detail_address"] == "科技园3号"

    default_response = client.patch(
        f"/addresses/{second_id}/default",
        headers=auth_headers,
    )
    assert default_response.status_code == 200
    assert default_response.json()["is_default"] is True

    old_address_response = client.get(
        f"/addresses/{first_id}",
        headers=auth_headers,
    )
    assert old_address_response.json()["is_default"] is False


def test_user_cannot_read_other_users_address(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """地址ID存在，但不属于当前用户时仍然返回404。"""

    address_id = client.post(
        "/addresses/",
        headers=auth_headers,
        json=address_body("小明", "科技园1号"),
    ).json()["id"]
    other_headers = register_other_user(client)

    response = client.get(
        f"/addresses/{address_id}",
        headers=other_headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "收货地址不存在",
    }


def test_delete_default_address_promotes_remaining_address(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """删除默认地址后，剩余地址应自动产生新的默认地址。"""

    first_id = client.post(
        "/addresses/",
        headers=auth_headers,
        json=address_body("小明", "科技园1号"),
    ).json()["id"]
    second_id = client.post(
        "/addresses/",
        headers=auth_headers,
        json=address_body("小明", "科技园2号"),
    ).json()["id"]

    delete_response = client.delete(
        f"/addresses/{first_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    remaining_response = client.get(
        f"/addresses/{second_id}",
        headers=auth_headers,
    )
    assert remaining_response.status_code == 200
    assert remaining_response.json()["is_default"] is True
