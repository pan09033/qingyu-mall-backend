from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.product import Product
from app.rag.ingestion.product import (
    build_product_knowledge_document,
)
from app.rag.models.knowledge_chunk import KnowledgeChunk
from app.rag.providers.embedding import (
    LocalBgeEmbeddingProvider,
)
from app.rag.repositories.knowledge_chunk import (
    delete_stale_knowledge_chunks,
    upsert_knowledge_chunk,
)
from app.rag.repositories.product_source import (
    get_product_batch_for_knowledge_sync,
)


def sync_product_knowledge(
    rag_db: Session,
    product: Product,
    embedding_provider: LocalBgeEmbeddingProvider,
) -> KnowledgeChunk:
    """把一个商城商品同步到 PostgreSQL 知识库。"""

    document = build_product_knowledge_document(product)

    embeddings = embedding_provider.embed_documents(
        [document.content]
    )

    if len(embeddings) != 1:
        raise RuntimeError(
            "Embedding Provider没有返回一条商品向量"
        )

    try:
        knowledge_chunk = upsert_knowledge_chunk(
            rag_db,
            document,
            embeddings[0],
        )
        rag_db.commit()

    except SQLAlchemyError:
        rag_db.rollback()
        raise

    return knowledge_chunk


def sync_product_knowledge_batch(
    mysql_db: Session,
    rag_db: Session,
    embedding_provider: LocalBgeEmbeddingProvider,
    after_id: int = 0,
    limit: int = 100,
) -> tuple[int, int | None]:
    """分批读取并同步商品知识。"""

    products = get_product_batch_for_knowledge_sync(
        mysql_db,
        after_id=after_id,
        limit=limit,
    )

    if not products:
        return 0, None

    documents = [
        build_product_knowledge_document(product)
        for product in products
    ]

    embeddings = embedding_provider.embed_documents(
        [
            document.content
            for document in documents
        ]
    )

    if len(embeddings) != len(documents):
        raise RuntimeError(
            "Embedding数量与商品知识数量不匹配："
            f"文档{len(documents)}条，"
            f"向量{len(embeddings)}条"
        )

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

        rag_db.commit()

    except Exception:
        rag_db.rollback()
        raise

    return len(documents), products[-1].id


def delete_product_knowledge(
    rag_db: Session,
    product_id: int,
) -> None:
    """删除指定商品的全部知识分段。"""

    # rag_db：PostgreSQL数据库会话
    # product_id：要删除知识的商品ID
    if product_id <= 0:
        raise ValueError("商品ID必须大于0")

    try:
        delete_stale_knowledge_chunks(
            db=rag_db,
            source_type="product",       # 只处理商品知识
            source_id=str(product_id),   # 知识来源ID以字符串保存
            active_document_keys=set(),  # 不保留该商品的任何分段
        )
        rag_db.commit()

    except SQLAlchemyError:
        rag_db.rollback()
        raise
