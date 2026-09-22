from pathlib import Path

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


def test_rag_database_credentials_are_optional_at_startup() -> None:
    settings = build_settings()

    assert settings.rag_db_host == "127.0.0.1"
    assert settings.rag_db_port == 5432
    assert settings.rag_db_name == "mall_rag"
    assert settings.rag_db_user == "mall_rag_app"
    assert settings.rag_db_password.get_secret_value() == ""
    assert settings.rag_db_connect_timeout_seconds == 3


def test_rag_embedding_uses_safe_defaults() -> None:
    settings = build_settings()

    assert settings.rag_embedding_model_path is None
    assert settings.rag_embedding_dimension == 512
    assert settings.rag_embedding_device == "cpu"
    assert settings.rag_minimum_similarity == 0.50
    assert settings.rag_retrieval_limit == 5


def test_rag_embedding_model_path_is_parsed() -> None:
    settings = build_settings(
        rag_embedding_model_path=(
            "D:/models/bge-small-zh-v1.5"
        ),
    )

    assert settings.rag_embedding_model_path == Path(
        "D:/models/bge-small-zh-v1.5"
    )


def test_deepseek_uses_safe_defaults() -> None:
    settings = build_settings()

    assert settings.deepseek_api_key.get_secret_value() == ""
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_model == "deepseek-flash"
    assert settings.deepseek_timeout_seconds == 30.0
    assert settings.deepseek_max_tokens == 512


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("deepseek_timeout_seconds", 0),
        ("deepseek_max_tokens", 0),
        ("deepseek_max_tokens", 4097),
    ],
)
def test_deepseek_rejects_invalid_limits(
    field_name: str,
    invalid_value: int,
) -> None:
    with pytest.raises(ValidationError):
        build_settings(**{field_name: invalid_value})


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("rag_minimum_similarity", -1.01),
        ("rag_minimum_similarity", 1.01),
        ("rag_retrieval_limit", 0),
        ("rag_retrieval_limit", 21),
    ],
)
def test_rag_retrieval_rejects_invalid_limits(
    field_name: str,
    invalid_value: float | int,
) -> None:
    with pytest.raises(ValidationError):
        build_settings(**{field_name: invalid_value})


@pytest.mark.parametrize("port", [0, 65536])
def test_rabbitmq_port_must_be_valid(port: int) -> None:
    with pytest.raises(ValidationError):
        build_settings(rabbitmq_port=port)
