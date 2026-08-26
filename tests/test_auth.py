from fastapi import status
from fastapi.testclient import TestClient


def test_register_user(
    client: TestClient,
) -> None:
    request_data = {
        "name": "测试用户",
        "age": 20,
        "username": "test_user",
        "password": "abc123456",
    }

    response = client.post(
        "/auth/register",
        json=request_data,
    )

    assert response.status_code == (
        status.HTTP_201_CREATED
    )

    response_data = response.json()

    assert response_data["name"] == "测试用户"
    assert response_data["age"] == 20
    assert response_data["username"] == "test_user"
    assert isinstance(response_data["id"], int)

    # 响应中绝对不能包含密码。
    assert "password" not in response_data
    assert "hashed_password" not in response_data


def test_register_duplicate_username(
    client: TestClient,
) -> None:
    request_data = {
        "name": "第一个用户",
        "age": 20,
        "username": "duplicate_user",
        "password": "abc123456",
    }

    first_response = client.post(
        "/auth/register",
        json=request_data,
    )

    second_response = client.post(
        "/auth/register",
        json={
            "name": "第二个用户",
            "age": 21,
            # 会被清理成 duplicate_user。
            "username": " DUPLICATE_USER ",
            "password": "abc123456",
        },
    )

    assert first_response.status_code == (
        status.HTTP_201_CREATED
    )
    assert second_response.status_code == (
        status.HTTP_409_CONFLICT
    )
    assert second_response.json() == {
        "detail": "用户名已存在",
    }


def test_register_invalid_data(
    client: TestClient,
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "name": "年龄错误",
            "age": 5,
            "username": "invalid_user",
            "password": "123",
        },
    )

    assert response.status_code == (
        status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    assert "detail" in response.json()


def test_login_user(
    client: TestClient,
) -> None:
    # 每个测试使用全新的数据库，因此先注册登录所需的用户。
    client.post(
        "/auth/register",
        json={
            "name": "登录测试用户",
            "age": 20,
            "username": "login_user",
            "password": "abc123456",
        },
    )

    response = client.post(
        "/auth/login",
        # OAuth2PasswordRequestForm 接收表单数据。
        data={
            "username": "login_user",
            "password": "abc123456",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()

    assert response_data["token_type"] == "bearer"
    assert isinstance(
        response_data["access_token"],
        str,
    )
    assert response_data["access_token"]


def test_login_wrong_password(
    client: TestClient,
) -> None:
    client.post(
        "/auth/register",
        json={
            "name": "密码测试用户",
            "age": 20,
            "username": "password_user",
            "password": "abc123456",
        },
    )

    response = client.post(
        "/auth/login",
        data={
            "username": "password_user",
            "password": "wrong-password",
        },
    )

    assert response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )
    assert response.json() == {
        "detail": "用户名或密码错误",
    }
    assert response.headers["www-authenticate"] == (
        "Bearer"
    )


def test_get_current_user(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.get(
        "/auth/me",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()

    assert response_data["name"] == "当前测试用户"
    assert response_data["age"] == 20
    assert response_data["username"] == "current_user"
    assert "password" not in response_data
    assert "hashed_password" not in response_data


def test_get_current_user_without_token(
    client: TestClient,
) -> None:
    response = client.get("/auth/me")

    assert response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )
    assert response.json() == {
        "detail": "Not authenticated",
    }


def test_get_current_user_with_invalid_token(
    client: TestClient,
) -> None:
    response = client.get(
        "/auth/me",
        headers={
            "Authorization": "Bearer invalid-token",
        },
    )

    assert response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )
    assert response.json() == {
        "detail": "无法验证登录凭证",
    }


def test_change_password_and_login_with_new_password(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """修改密码后，旧密码失效，新密码可以登录。"""

    response = client.patch(
        "/auth/me/password",
        headers=auth_headers,
        json={
            "current_password": "abc123456",
            "new_password": "newPassword123",
        },
    )

    assert response.status_code == (
        status.HTTP_204_NO_CONTENT
    )
    assert response.content == b""

    old_password_response = client.post(
        "/auth/login",
        data={
            "username": "current_user",
            "password": "abc123456",
        },
    )
    assert old_password_response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )

    new_password_response = client.post(
        "/auth/login",
        data={
            "username": "current_user",
            "password": "newPassword123",
        },
    )
    assert new_password_response.status_code == (
        status.HTTP_200_OK
    )


def test_change_password_with_wrong_current_password(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """当前密码错误时返回400。"""

    response = client.patch(
        "/auth/me/password",
        headers=auth_headers,
        json={
            "current_password": "wrong-password",
            "new_password": "newPassword123",
        },
    )

    assert response.status_code == (
        status.HTTP_400_BAD_REQUEST
    )
    assert response.json() == {
        "detail": "当前密码错误",
    }


def test_change_password_to_same_password(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """新旧密码相同时返回409。"""

    response = client.patch(
        "/auth/me/password",
        headers=auth_headers,
        json={
            "current_password": "abc123456",
            "new_password": "abc123456",
        },
    )

    assert response.status_code == (
        status.HTTP_409_CONFLICT
    )
    assert response.json() == {
        "detail": "新密码不能与当前密码相同",
    }


def test_change_password_without_token(
    client: TestClient,
) -> None:
    """未登录用户不能修改密码。"""

    response = client.patch(
        "/auth/me/password",
        json={
            "current_password": "abc123456",
            "new_password": "newPassword123",
        },
    )

    assert response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )
