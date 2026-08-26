from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def test_admin_can_get_user_and_missing_user(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
) -> None:
    """管理员可查询用户，不存在的用户返回404。"""

    current_user = db_session.scalar(
        select(User).where(
            User.username == "current_user",
        )
    )
    assert current_user is not None

    response = client.get(
        f"/users/{current_user.id}",
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == current_user.id
    assert "hashed_password" not in response.json()

    missing_response = client.get(
        "/users/999",
        headers=admin_headers,
    )
    assert missing_response.status_code == status.HTTP_404_NOT_FOUND
    assert missing_response.json() == {
        "detail": "用户不存在",
    }


def test_regular_user_cannot_get_admin_user_details(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """普通用户不能访问管理员用户详情接口。"""

    response = client.get(
        "/users/1",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_can_filter_paginate_and_get_user_details(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """管理员可筛选、分页并查看带订单的用户详情。"""

    first_user = client.post(
        "/auth/register",
        json={
            "name": "张三测试",
            "age": 20,
            "username": "user_list_zhang",
            "password": "abc123456",
        },
    ).json()
    client.post(
        "/auth/register",
        json={
            "name": "李四测试",
            "age": 21,
            "username": "user_list_li",
            "password": "abc123456",
        },
    )

    filter_response = client.get(
        "/users/",
        headers=admin_headers,
        params={"keyname": "张三"},
    )
    assert filter_response.status_code == status.HTTP_200_OK
    assert filter_response.json()["total"] == 1
    assert filter_response.json()["items"][0]["id"] == first_user["id"]

    page_response = client.get(
        "/users/",
        headers=admin_headers,
        params={
            "skip": 1,
            "limit": 1,
        },
    )
    assert page_response.status_code == status.HTTP_200_OK
    assert page_response.json()["total"] == 3
    assert page_response.json()["skip"] == 1
    assert page_response.json()["limit"] == 1
    assert len(page_response.json()["items"]) == 1

    details_response = client.get(
        f"/users/{first_user['id']}/details",
        headers=admin_headers,
    )
    assert details_response.status_code == status.HTTP_200_OK
    assert details_response.json()["id"] == first_user["id"]
    assert details_response.json()["orders"] == []

    missing_response = client.get(
        "/users/999/details",
        headers=admin_headers,
    )
    assert missing_response.status_code == status.HTTP_404_NOT_FOUND


def test_admin_can_update_other_role_but_not_demote_self(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
) -> None:
    """管理员可修改他人角色，但不能取消自己的管理员权限。"""

    target_user = client.post(
        "/auth/register",
        json={
            "name": "角色修改目标",
            "age": 22,
            "username": "role_target",
            "password": "abc123456",
        },
    ).json()

    response = client.patch(
        f"/users/{target_user['id']}/role",
        headers=admin_headers,
        json={"role": "admin"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["role"] == "admin"

    current_admin = db_session.scalar(
        select(User).where(
            User.username == "current_user",
        )
    )
    assert current_admin is not None

    self_response = client.patch(
        f"/users/{current_admin.id}/role",
        headers=admin_headers,
        json={"role": "user"},
    )
    assert self_response.status_code == status.HTTP_400_BAD_REQUEST
    assert self_response.json() == {
        "detail": "不能取消自己的管理员权限",
    }

    db_session.expire_all()
    assert db_session.get(User, current_admin.id).role == "admin"
