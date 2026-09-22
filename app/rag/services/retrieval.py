from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.rag.models.knowledge_chunk import KnowledgeChunk
from app.rag.providers.embedding import (
    LocalBgeEmbeddingProvider,
)
from app.rag.repositories.knowledge_chunk import (
    search_knowledge,
)


def retrieve_knowledge(
    rag_db: Session,
    embedding_provider: LocalBgeEmbeddingProvider,
    question: str,
    minimum_similarity: float,
    source_type: Literal["product", "policy"] | None = None,
    topic: str | None = None,
    max_price: Decimal | None = None,
    limit: int = 5,
) -> list[tuple[KnowledgeChunk, float]]:
    """检索达到最低相似度的商城知识。"""

    normalized_question = question.strip()

    if not normalized_question:
        raise ValueError("用户问题不能为空")

    if not -1 <= minimum_similarity <= 1:
        raise ValueError(
            "最低相似度必须在-1到1之间"
        )

    query_embedding = embedding_provider.embed_query(
        normalized_question
    )

    candidates = search_knowledge(
        rag_db,
        query_embedding=query_embedding,
        source_type=source_type,
        topic=topic,
        max_price=max_price,
        limit=limit,
    )

    return [
        (knowledge_chunk, similarity)
        for knowledge_chunk, similarity in candidates
        if similarity >= minimum_similarity
    ]
