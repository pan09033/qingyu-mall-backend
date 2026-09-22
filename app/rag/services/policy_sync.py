from pathlib import Path

from sqlalchemy.orm import Session

from app.rag.ingestion.policy import (
    build_policy_knowledge_documents,
)
from app.rag.providers.embedding import (
    LocalBgeEmbeddingProvider,
)
from app.rag.repositories.knowledge_chunk import (
    delete_stale_knowledge_chunks,
    upsert_knowledge_chunk,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
# PROJECT_ROOT：后端项目根目录

POLICY_DIRECTORY = (
    PROJECT_ROOT
    / "knowledge"
    / "policies"
)
# POLICY_DIRECTORY：商城规则文档目录

POLICY_SOURCES: dict[
    str,
    tuple[str, Path],
] = {
    "refund": (
        "refund_policy",
        POLICY_DIRECTORY / "refund_policy.md",
    ),
    "payment": (
        "payment_policy",
        POLICY_DIRECTORY / "payment_policy.md",
    ),
    "shipping": (
        "shipping_policy",
        POLICY_DIRECTORY / "shipping_policy.md",
    ),
}
# POLICY_SOURCES：规则主题与来源ID、文件路径的固定映射


def sync_policy_knowledge(
    rag_db: Session,
    embedding_provider: LocalBgeEmbeddingProvider,
    file_path: Path,
    source_id: str,
    topic: str,
) -> int:
    """切分并同步一份商城规则文档。"""

    documents = build_policy_knowledge_documents(
        file_path,
        source_id=source_id,
        topic=topic,
    )

    embeddings = embedding_provider.embed_documents(
        [
            document.content
            for document in documents
        ]
    )

    if len(embeddings) != len(documents):
        raise RuntimeError(
            "Embedding数量与规则分段数量不匹配："
            f"文档{len(documents)}条，"
            f"向量{len(embeddings)}条"
        )

    active_document_keys = {
        document.document_key
        for document in documents
    }

    try:
        for document, embedding in zip(
            documents,
            embeddings,
            strict=True,
        ):
            upsert_knowledge_chunk(
                rag_db,
                document,
                embedding,
            )

        delete_stale_knowledge_chunks(
            rag_db,
            source_type="policy",
            source_id=source_id,
            active_document_keys=active_document_keys,
        )

        rag_db.commit()

    except Exception:
        rag_db.rollback()
        raise

    return len(documents)


def rebuild_policy_knowledge_by_topic(
    rag_db: Session,
    embedding_provider: LocalBgeEmbeddingProvider,
    topic: str,
) -> tuple[str, int]:
    """根据允许的规则主题重建一份规则知识。"""

    normalized_topic = topic.strip().lower()
    # normalized_topic：去除空白并转成小写的规则主题

    policy_source = POLICY_SOURCES.get(
        normalized_topic
    )
    # policy_source：主题对应的来源ID和固定文件路径

    if policy_source is None:
        raise ValueError(
            f"不支持的规则主题：{normalized_topic}"
        )

    source_id, file_path = policy_source
    # source_id：规则文档来源标识
    # file_path：规则文档的固定路径

    synced_chunk_count = sync_policy_knowledge(
        rag_db=rag_db,
        embedding_provider=embedding_provider,
        file_path=file_path,
        source_id=source_id,
        topic=normalized_topic,
    )
    # synced_chunk_count：成功同步的知识分段数量

    return source_id, synced_chunk_count
