from collections.abc import Generator

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import settings

DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=settings.db_user,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port,
    database=settings.db_name,
    query={
        "charset": "utf8mb4",
    },
)

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    echo=settings.sql_echo,
    pool_pre_ping=True,
)


# 所有数据库模型的父类
class Base(DeclarativeBase):
    pass


# 为每次请求提供独立的Session
def get_db() -> Generator[
    Session,
    None,
    None,
]:
    with Session(engine) as session:
        yield session
