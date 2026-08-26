from typing import Literal

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """应用配置。"""

    db_user: str
    db_password: str
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str
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
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    payment_callback_secret: str = (
        "development-payment-secret"
    )
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

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

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
