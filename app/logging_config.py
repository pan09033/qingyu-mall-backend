from logging.config import dictConfig


def setup_logging(
    log_level: str = "INFO",
) -> None:
    """配置项目统一日志格式。"""

    log_level = log_level.upper()

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": (
                        "%(asctime)s | "
                        "%(levelname)s | "
                        "%(name)s | "
                        "%(message)s"
                    ),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": log_level,
                    "formatter": "standard",
                },
            },
            "root": {
                "level": log_level,
                "handlers": [
                    "console",
                ],
            },
        }
    )
