from unittest.mock import Mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import redis_client
from app.services.login_rate_limit import (
    RECORD_LOGIN_FAILURE_SCRIPT,
)


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


def test_login_failure_uses_atomic_redis_script(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """登录失败时一次性提交 Lua 脚本和全部参数。"""

    client.post(
        "/auth/register",
        json={
            "name": "登录限流测试用户",
            "age": 20,
            "username": "rate_limit_user",
            "password": "abc123456",
        },
    )

    mock_get = Mock(return_value=None)
    mock_eval = Mock(return_value=0)
    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(
        redis_client,
        "eval",
        mock_eval,
    )

    response = client.post(
        "/auth/login",
        data={
            "username": "rate_limit_user",
            "password": "wrong-password",
        },
    )

    lock_key = "rate_limit:login:lock:testclient"
    failure_key = "rate_limit:login:fail:testclient"
    level_key = "rate_limit:login:level:testclient"
    assert response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )
    mock_get.assert_called_once_with(lock_key)
    mock_eval.assert_called_once_with(
        RECORD_LOGIN_FAILURE_SCRIPT,
        3,
        failure_key,
        lock_key,
        level_key,
        settings.login_max_failures,
        settings.login_failure_window_seconds,
        settings.login_lock_level_ttl_seconds,
        settings.login_lock_durations_seconds[0],
        settings.login_lock_durations_seconds[1],
        settings.login_lock_durations_seconds[2],
    )


def test_login_rate_limit_returns_429(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """失败次数达到上限时，在验证密码前拒绝登录。"""

    mock_get = Mock(
        return_value=str(settings.login_max_failures)
    )
    mock_ttl = Mock(return_value=37)
    mock_incr = Mock(return_value=6)
    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(redis_client, "ttl", mock_ttl)
    monkeypatch.setattr(redis_client, "incr", mock_incr)

    response = client.post(
        "/auth/login",
        data={
            "username": "any_user",
            "password": "any_password",
        },
    )

    lock_key = "rate_limit:login:lock:testclient"
    assert response.status_code == (
        status.HTTP_429_TOO_MANY_REQUESTS
    )
    assert response.json() == {
        "detail": "登录失败次数过多，请稍后再试",
    }
    assert response.headers["retry-after"] == "37"
    mock_get.assert_called_once_with(lock_key)
    mock_ttl.assert_called_once_with(lock_key)
    mock_incr.assert_not_called()


def test_successful_login_clears_failure_counter(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """登录成功后清除同一客户端的旧失败计数。"""

    client.post(
        "/auth/register",
        json={
            "name": "成功登录清除计数用户",
            "age": 20,
            "username": "clear_counter_user",
            "password": "abc123456",
        },
    )

    mock_get = Mock(return_value=None)
    mock_delete = Mock(return_value=1)
    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(
        redis_client,
        "delete",
        mock_delete,
    )

    response = client.post(
        "/auth/login",
        data={
            "username": "clear_counter_user",
            "password": "abc123456",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    mock_delete.assert_called_once_with(
        "rate_limit:login:fail:testclient",
        "rate_limit:login:lock:testclient",
        "rate_limit:login:level:testclient",
    )


def test_login_continues_when_rate_limit_read_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis 无法读取计数时，正确密码仍然可以登录。"""

    client.post(
        "/auth/register",
        json={
            "name": "读取计数降级测试用户",
            "age": 20,
            "username": "redis_get_error_user",
            "password": "abc123456",
        },
    )

    monkeypatch.setattr(
        redis_client,
        "get",
        Mock(side_effect=RedisError("test error")),
    )

    response = client.post(
        "/auth/login",
        data={
            "username": "redis_get_error_user",
            "password": "abc123456",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["access_token"]


def test_wrong_password_stays_401_when_counter_write_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis 无法记录失败次数时，保留原本的认证错误。"""

    client.post(
        "/auth/register",
        json={
            "name": "写入计数降级测试用户",
            "age": 20,
            "username": "redis_incr_error_user",
            "password": "abc123456",
        },
    )

    monkeypatch.setattr(
        redis_client,
        "eval",
        Mock(side_effect=RedisError("test error")),
    )

    response = client.post(
        "/auth/login",
        data={
            "username": "redis_incr_error_user",
            "password": "wrong-password",
        },
    )

    assert response.status_code == (
        status.HTTP_401_UNAUTHORIZED
    )
    assert response.json() == {
        "detail": "用户名或密码错误",
    }


def test_rate_limit_uses_default_time_when_ttl_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已超过限制时，TTL 故障仍返回带默认时间的 429。"""

    monkeypatch.setattr(
        redis_client,
        "get",
        Mock(return_value=str(settings.login_max_failures)),
    )
    monkeypatch.setattr(
        redis_client,
        "ttl",
        Mock(side_effect=RedisError("test error")),
    )

    response = client.post(
        "/auth/login",
        data={
            "username": "any_user",
            "password": "any_password",
        },
    )

    assert response.status_code == (
        status.HTTP_429_TOO_MANY_REQUESTS
    )
    assert response.headers["retry-after"] == str(
        settings.login_lock_durations_seconds[0]
    )


def test_successful_login_continues_when_counter_delete_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis 无法清理计数时，验证成功的用户仍获得 Token。"""

    client.post(
        "/auth/register",
        json={
            "name": "删除计数降级测试用户",
            "age": 20,
            "username": "redis_delete_error_user",
            "password": "abc123456",
        },
    )

    monkeypatch.setattr(
        redis_client,
        "delete",
        Mock(side_effect=RedisError("test error")),
    )

    response = client.post(
        "/auth/login",
        data={
            "username": "redis_delete_error_user",
            "password": "abc123456",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["access_token"]


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
