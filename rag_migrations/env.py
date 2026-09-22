from logging.config import fileConfig

from alembic import context

from app.rag.database import (
    RAG_DATABASE_URL,
    RagBase,
    rag_engine,
)
from app.rag.models.knowledge_chunk import (  # noqa: F401
    KnowledgeChunk,
)


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = RagBase.metadata


def run_migrations_offline() -> None:
    """不连接 PostgreSQL，只生成迁移 SQL。"""

    database_url = RAG_DATABASE_URL.render_as_string(
        hide_password=True,
    )

    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
        version_table="rag_alembic_version",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """连接 PostgreSQL 并执行迁移。"""

    with rag_engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            version_table="rag_alembic_version",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
