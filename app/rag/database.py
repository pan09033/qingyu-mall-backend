from collections.abc import Generator

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import settings


RAG_DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=settings.rag_db_user,
    password=settings.rag_db_password.get_secret_value(),
    host=settings.rag_db_host,
    port=settings.rag_db_port,
    database=settings.rag_db_name,
)


rag_engine = create_engine(
    RAG_DATABASE_URL,
    echo=settings.sql_echo,
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": (
            settings.rag_db_connect_timeout_seconds
        ),
    },
)


class RagBase(DeclarativeBase):
    """所有 PostgreSQL RAG 模型的父类。"""

    pass


def get_rag_db() -> Generator[
    Session,
    None,
    None,
]:
    """为一次 RAG 操作提供数据库会话。"""

    with Session(rag_engine) as session:
        yield session