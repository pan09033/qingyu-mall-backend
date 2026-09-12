import pytest
from pydantic import ValidationError

from app.config import Settings


def build_settings(**overrides: object) -> Settings:
    """创建不读取本机 .env 的最小测试配置。"""

    values: dict[str, object] = {
        "db_user": "test-user",
        "db_password": "test-password",
        "db_name": "test-database",
        "redis_password": "redis-password",
        "rabbitmq_username": "test-rabbitmq-user",
        "rabbitmq_password": "test-rabbitmq-password",
        "jwt_secret_key": "j" * 32,
        "payment_callback_secret": "p" * 32,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "durations",
    [(), (60,), (60, 300), (60, 300, 0)],
)
def test_login_lock_durations_require_three_positive_values(
    durations: tuple[int, ...],
) -> None:
    with pytest.raises(ValidationError):
        build_settings(
            login_lock_durations_seconds=durations,
        )


def test_production_rejects_shared_secrets() -> None:
    with pytest.raises(ValidationError):
        build_settings(
            app_env="production",
            jwt_secret_key="s" * 32,
            payment_callback_secret="s" * 32,
        )


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        build_settings(
            app_env="production",
            cors_origins=["*"],
        )


def test_rabbitmq_uses_local_defaults() -> None:
    settings = build_settings()

    assert settings.rabbitmq_host == "127.0.0.1"
    assert settings.rabbitmq_port == 5672
    assert settings.rabbitmq_virtual_host == "/"


@pytest.mark.parametrize("port", [0, 65536])
def test_rabbitmq_port_must_be_valid(port: int) -> None:
    with pytest.raises(ValidationError):
        build_settings(rabbitmq_port=port)
