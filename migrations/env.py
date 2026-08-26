from logging.config import fileConfig

from alembic import context

from app.database import (
    Base,
    DATABASE_URL,
    engine,
)

# 虽然代码中没有直接使用Product，
# 但导入后，它才会注册到Base.metadata中
from app.models.product import Product  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.order_item import OrderItem  # noqa: F401
from app.models.address import Address  # noqa: F401
from app.models.cart_item import CartItem  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.refund_request import RefundRequest  # noqa: F401
# Alembic配置对象
config = context.config


# 加载alembic.ini中的日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Alembic根据它读取所有数据库模型
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """不直接连接数据库，只生成SQL。"""

    database_url = DATABASE_URL.render_as_string(
        hide_password=False,
    )

    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """连接数据库并执行迁移。"""

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
