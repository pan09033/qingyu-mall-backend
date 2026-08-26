from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.user import User


# sqlite:// 表示只存在于内存中的临时数据库
test_engine = create_engine(
    "sqlite://",
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)


@pytest.fixture
def client() -> Generator[
    TestClient,
    None,
    None,
]:
    # 每个测试开始前创建表
    Base.metadata.create_all(
        bind=test_engine,
    )

    # 使用测试数据库替换项目的 MySQL 数据库依赖
    def override_get_db():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db] = (
        override_get_db
    )

    # yield 前是测试准备，yield 返回测试客户端
    with TestClient(app) as test_client:
        yield test_client

    # 每个测试结束后恢复依赖并删除测试表
    app.dependency_overrides.clear()

    Base.metadata.drop_all(
        bind=test_engine,
    )


@pytest.fixture
def auth_headers(
    client: TestClient,
) -> dict[str, str]:
    """注册并登录用户，返回 Bearer Token 请求头。"""

    register_response = client.post(
        "/auth/register",
        json={
            "name": "当前测试用户",
            "age": 20,
            "username": "current_user",
            "password": "abc123456",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        data={
            "username": "current_user",
            "password": "abc123456",
        },
    )
    assert login_response.status_code == 200

    access_token = login_response.json()[
        "access_token"
    ]

    return {
        "Authorization": f"Bearer {access_token}",
    }


@pytest.fixture
def shipping_address_id(
    client: TestClient,
    auth_headers: dict[str, str],
) -> int:
    """为当前测试用户创建一条收货地址。"""

    response = client.post(
        "/addresses/",
        headers=auth_headers,
        json={
            "receiver_name": "订单测试用户",
            "phone": "13800138000",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail_address": "科技园1号",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def admin_headers(
    auth_headers: dict[str, str],
    db_session: Session,
) -> dict[str, str]:
    """把已经登录的测试用户设置为管理员。"""

    user = db_session.scalar(
        select(User).where(
            User.username == "current_user",
        )
    )
    assert user is not None

    user.role = "admin"
    db_session.commit()

    return auth_headers


@pytest.fixture
def db_session(
    client: TestClient,
) -> Generator[Session, None, None]:
    """提供与 TestClient 共用同一测试引擎的数据库会话。"""

    with Session(test_engine) as session:
        yield session
