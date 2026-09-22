from decimal import Decimal
from typing import Literal

from sqlalchemy import Numeric, cast, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.rag.models.knowledge_chunk import KnowledgeChunk
from app.schemas.rag import KnowledgeDocument


def upsert_knowledge_chunk(
    db: Session,
    document: KnowledgeDocument,
    embedding: list[float],
) -> KnowledgeChunk:
    """新增知识分段，或用最新内容更新已有分段。"""

    if len(embedding) != settings.rag_embedding_dimension:
        raise ValueError(
            "Embedding维度不匹配："
            f"预期{settings.rag_embedding_dimension}，"
            f"实际{len(embedding)}"
        )

    insert_statement = insert(KnowledgeChunk).values(
        document_key=document.document_key,
        source_type=document.source_type,
        source_id=document.source_id,
        title=document.title,
        content=document.content,
        chunk_index=document.chunk_index,
        metadata_json=document.metadata.model_dump(mode="json"),
        embedding=embedding,
    )

    upsert_statement = insert_statement.on_conflict_do_update(
        index_elements=[
            KnowledgeChunk.document_key,
        ],
        set_={
            "source_type": insert_statement.excluded.source_type,
            "source_id": insert_statement.excluded.source_id,
            "title": insert_statement.excluded.title,
            "content": insert_statement.excluded.content,
            "chunk_index": insert_statement.excluded.chunk_index,
            "metadata": insert_statement.excluded.metadata,
            "embedding": insert_statement.excluded.embedding,
        },
    ).returning(KnowledgeChunk)

    return db.scalars(upsert_statement).one()


def search_knowledge(
    db: Session,
    query_embedding: list[float],
    source_type: Literal["product", "policy"] | None = None,
    topic: str | None = None,
    max_price: Decimal | None = None,
    limit: int = 5,
) -> list[tuple[KnowledgeChunk, float]]:
    """从指定类型或全部商城知识中检索相似内容。"""

    if len(query_embedding) != settings.rag_embedding_dimension:
        raise ValueError(
            "问题Embedding维度不匹配："
            f"预期{settings.rag_embedding_dimension}，"
            f"实际{len(query_embedding)}"
        )

    if limit < 1:
        raise ValueError("检索数量必须大于0")

    if (
        max_price is not None
        and source_type != "product"
    ):
        raise ValueError(
            "预算过滤只能用于商品知识"
        )

    normalized_topic = None

    if topic is not None:
        if source_type != "policy":
            raise ValueError(
                "规则主题过滤只能用于规则知识"
            )

        normalized_topic = topic.strip()

        if not normalized_topic:
            raise ValueError("规则主题不能为空")

    distance = KnowledgeChunk.embedding.cosine_distance(
        query_embedding
    )
    similarity = (1 - distance).label("similarity")

    statement = select(
        KnowledgeChunk,
        similarity,
    )

    if source_type is not None:
        statement = statement.where(
            KnowledgeChunk.source_type == source_type,
        )
    if normalized_topic is not None:
        statement = statement.where(
            KnowledgeChunk.metadata_json["topic"].astext
            == normalized_topic,
        )
    if max_price is not None:
        metadata_price = cast(
            KnowledgeChunk.metadata_json["price"].astext,
            Numeric(10, 2),
        )
        statement = statement.where(
            metadata_price <= max_price,
        )

    statement = (
        statement
        .order_by(distance.asc())
        .limit(limit)
    )

    rows = db.execute(statement).all()

    return [
        (knowledge_chunk, float(similarity_score))
        for knowledge_chunk, similarity_score in rows
    ]


def delete_stale_knowledge_chunks(
    db: Session,
    source_type: str,
    source_id: str,
    active_document_keys: set[str],
) -> None:
    """删除同一来源中已经不存在的知识分段。"""

    normalized_source_type = source_type.strip()
    normalized_source_id = source_id.strip()

    if not normalized_source_type:
        raise ValueError("知识来源类型不能为空")

    if not normalized_source_id:
        raise ValueError("知识来源ID不能为空")

    statement = delete(KnowledgeChunk).where(
        KnowledgeChunk.source_type
        == normalized_source_type,
        KnowledgeChunk.source_id
        == normalized_source_id,
    )

    if active_document_keys:
        statement = statement.where(
            KnowledgeChunk.document_key.not_in(
                sorted(active_document_keys)
            )
        )

    db.execute(statement)
