from pathlib import Path
from typing import Literal

from pydantic import (
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """应用配置。"""

    db_user: str
    db_password: str
    db_host: str = "127.0.0.1"
    db_port: int = Field(default=3306, ge=1, le=65535)
    db_name: str
    rag_db_host: str = "127.0.0.1"
    rag_db_port: int = Field(default=5432, ge=1, le=65535)
    rag_db_name: str = "mall_rag"
    rag_db_user: str = "mall_rag_app"
    rag_db_password: SecretStr = SecretStr("")
    rag_db_connect_timeout_seconds: int = Field(
        default=3,
        ge=1,
    )
    rag_embedding_model_path: Path | None = None
    rag_embedding_dimension: int = Field(
        default=512,
        ge=1,
    )
    rag_embedding_device: Literal["cpu", "cuda"] = "cpu"
    rag_minimum_similarity: float = Field(
        default=0.50,
        ge=-1,
        le=1,
    )
    rag_retrieval_limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )
    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
    )
    deepseek_max_tokens: int = Field(
        default=512,
        ge=1,
        le=4096,
    )
    redis_host: str = "127.0.0.1"
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_password: str
    redis_protocol: Literal[2, 3] = 2
    redis_connect_timeout_seconds: float = Field(
        default=1.0,
        gt=0,
    )
    redis_socket_timeout_seconds: float = Field(
        default=1.0,
        gt=0,
    )

    login_max_failures: int = Field(default=5, ge=1)
    login_failure_window_seconds: int = Field(default=300, ge=1)
    login_lock_durations_seconds: tuple[int, ...] = (
        60,
        300,
        900,
    )
    login_lock_level_ttl_seconds: int = Field(
        default=86400,
        ge=1,
    )
    rabbitmq_host: str = "127.0.0.1"
    rabbitmq_port: int = Field(default=5672, ge=1, le=65535)
    rabbitmq_username: str
    rabbitmq_password: str
    rabbitmq_virtual_host: str = "/"
    minio_endpoint: str = "127.0.0.1:9000"
    minio_public_base_url: str = "http://127.0.0.1:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "product-media"
    minio_secure: bool = False
    app_env: Literal[
        "development",
        "testing",
        "production",
    ] = "development"

    log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"
    sql_echo: bool = False
    # jwt
    jwt_secret_key: str
    jwt_algorithm: Literal[
        "HS256",
        "HS384",
        "HS512",
    ] = "HS256"
    access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
    )
    payment_callback_secret: str = (
        "development-payment-secret"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    @field_validator("redis_protocol", mode="before")
    @classmethod
    def parse_redis_protocol(cls, value: object) -> object:
        """环境变量是字符串，先转换再校验允许的协议版本。"""

        if isinstance(value, str) and value in ("2", "3"):
            return int(value)
        return value

    @field_validator("login_lock_durations_seconds")
    @classmethod
    def validate_login_lock_durations(
        cls,
        durations: tuple[int, ...],
    ) -> tuple[int, ...]:
        """Lua 限流脚本固定使用三级锁定时长。"""

        if len(durations) != 3 or any(
            duration <= 0 for duration in durations
        ):
            raise ValueError(
                "LOGIN_LOCK_DURATIONS_SECONDS "
                "必须包含三个正整数"
            )
        return durations

    @model_validator(mode="after")
    def validate_production_settings(
        self,
    ) -> "Settings":
        """生产环境拒绝明显不安全的配置。"""

        if self.app_env != "production":
            return self

        if self.sql_echo:
            raise ValueError(
                "生产环境不能启用 SQL_ECHO"
            )

        if len(self.jwt_secret_key) < 32:
            raise ValueError(
                "生产环境 JWT_SECRET_KEY "
                "至少需要 32 个字符"
            )

        if len(self.payment_callback_secret) < 32:
            raise ValueError(
                "生产环境 PAYMENT_CALLBACK_SECRET "
                "至少需要 32 个字符"
            )

        if self.jwt_secret_key == self.payment_callback_secret:
            raise ValueError(
                "生产环境 JWT 与支付回调不能共用密钥"
            )

        if "*" in self.cors_origins:
            raise ValueError(
                "生产环境 CORS_ORIGINS 不能包含通配符"
            )

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
