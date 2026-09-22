from sqlalchemy.orm import Session

from app.config import settings
from app.rag.database import rag_engine
from app.rag.providers.factory import (
    get_chat_provider,
    get_embedding_provider,
)
from app.rag.services.qa import answer_question


def main() -> None:
    question = "我的退款到账了吗？"

    with Session(rag_engine) as rag_db:
        response = answer_question(
            rag_db=rag_db,
            embedding_provider_factory=get_embedding_provider,
            # embedding_provider_factory：按需获取BGE的函数
            chat_provider_factory=get_chat_provider,
            # chat_provider_factory：按需获取DeepSeek Provider的函数
            question=question,
            minimum_similarity=(
                settings.rag_minimum_similarity
            ),
            limit=settings.rag_retrieval_limit,
        )

    print(f"回答：{response.answer}")
    print("引用来源：")

    for source in response.sources:
        print(
            f"[资料{source.citation_number}] "
            f"{source.title}"
        )


if __name__ == "__main__":
    main()
