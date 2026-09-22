from sqlalchemy.orm import Session

from app.config import settings
from app.rag.database import rag_engine
from app.rag.providers.factory import get_embedding_provider
from app.rag.services.query_analysis import (
    infer_knowledge_scope,
)
from app.rag.services.retrieval import retrieve_knowledge


def main() -> None:
    question = "我的订单使用哪家快递发货？"

    source_type, topic = infer_knowledge_scope(
        question
    )

    with Session(rag_engine) as rag_db:
        matches = retrieve_knowledge(
            rag_db=rag_db,
            embedding_provider=get_embedding_provider(),
            question=question,
            minimum_similarity=(
                settings.rag_minimum_similarity
            ),
            source_type=source_type,
            topic=topic,
            limit=settings.rag_retrieval_limit,
        )

    print(
        f"检索范围：{source_type}, "
        f"主题：{topic}"
    )

    for chunk, similarity in matches:
        print(
            f"{chunk.document_key}，"
            f"相似度：{similarity:.3f}"
        )
        print(chunk.content)
        print()


if __name__ == "__main__":
    main()