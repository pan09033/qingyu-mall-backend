from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.category import Category
from app.models.product import Product
from app.rag.providers.embedding import (
    LocalBgeEmbeddingProvider,
)
from app.rag.services.product_sync import (
    sync_product_knowledge,
    sync_product_knowledge_batch,
)


def build_product(
    product_id: int = 12,
    name: str = "静音降噪蓝牙耳机",
) -> Product:
    category = Category(
        id=3,
        name="耳机",
        description="耳机分类",
    )
    return Product(
        id=product_id,
        name=name,
        price=Decimal("399.00"),
        stock=10,
        description="适合办公室使用",
        category_id=category.id,
        category=category,
    )


def test_sync_product_knowledge_runs_steps_in_order() -> None:
    events: list[str] = []
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    embedding = [0.1] * settings.rag_embedding_dimension
    expected_chunk = object()

    def embed_documents(texts: list[str]) -> list[list[float]]:
        events.append("embed")
        assert texts == [
            "商品名称：静音降噪蓝牙耳机。"
            "商品分类：耳机。"
            "商品描述：适合办公室使用"
        ]
        return [embedding]

    provider.embed_documents.side_effect = embed_documents
    rag_db.commit.side_effect = lambda: events.append("commit")

    with patch(
        "app.rag.services.product_sync.upsert_knowledge_chunk",
    ) as upsert:
        def save_chunk(*args: object) -> object:
            events.append("upsert")
            return expected_chunk

        upsert.side_effect = save_chunk

        result = sync_product_knowledge(
            rag_db,
            build_product(),
            provider,
        )

    assert events == ["embed", "upsert", "commit"]
    assert result is expected_chunk
    rag_db.rollback.assert_not_called()


def test_sync_product_knowledge_rejects_missing_embedding() -> None:
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    provider.embed_documents.return_value = []

    with patch(
        "app.rag.services.product_sync.upsert_knowledge_chunk",
    ) as upsert:
        with pytest.raises(
            RuntimeError,
            match="没有返回一条商品向量",
        ):
            sync_product_knowledge(
                rag_db,
                build_product(),
                provider,
            )

    upsert.assert_not_called()
    rag_db.commit.assert_not_called()


def test_sync_product_knowledge_rolls_back_database_error() -> None:
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    provider.embed_documents.return_value = [
        [0.1] * settings.rag_embedding_dimension
    ]
    database_error = SQLAlchemyError("写入失败")

    with patch(
        "app.rag.services.product_sync.upsert_knowledge_chunk",
        side_effect=database_error,
    ):
        with pytest.raises(SQLAlchemyError) as error_info:
            sync_product_knowledge(
                rag_db,
                build_product(),
                provider,
            )

    assert error_info.value is database_error
    rag_db.rollback.assert_called_once_with()
    rag_db.commit.assert_not_called()


def test_sync_product_batch_embeds_all_documents_once() -> None:
    mysql_db = Mock(spec=Session)
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    products = [
        build_product(12, "静音降噪蓝牙耳机"),
        build_product(13, "通勤蓝牙耳机"),
    ]
    embeddings = [
        [0.1] * settings.rag_embedding_dimension,
        [0.2] * settings.rag_embedding_dimension,
    ]
    provider.embed_documents.return_value = embeddings

    with (
        patch(
            "app.rag.services.product_sync."
            "get_product_batch_for_knowledge_sync",
            return_value=products,
        ) as get_batch,
        patch(
            "app.rag.services.product_sync.upsert_knowledge_chunk",
        ) as upsert,
    ):
        result = sync_product_knowledge_batch(
            mysql_db,
            rag_db,
            provider,
            after_id=7,
            limit=2,
        )

    get_batch.assert_called_once_with(
        mysql_db,
        after_id=7,
        limit=2,
    )
    provider.embed_documents.assert_called_once_with(
        [
            "商品名称：静音降噪蓝牙耳机。"
            "商品分类：耳机。"
            "商品描述：适合办公室使用",
            "商品名称：通勤蓝牙耳机。"
            "商品分类：耳机。"
            "商品描述：适合办公室使用",
        ]
    )
    assert upsert.call_count == 2
    assert upsert.call_args_list[0].args[2] is embeddings[0]
    assert upsert.call_args_list[1].args[2] is embeddings[1]
    rag_db.commit.assert_called_once_with()
    rag_db.rollback.assert_not_called()
    assert result == (2, 13)


def test_sync_product_batch_skips_empty_batch() -> None:
    mysql_db = Mock(spec=Session)
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)

    with (
        patch(
            "app.rag.services.product_sync."
            "get_product_batch_for_knowledge_sync",
            return_value=[],
        ),
        patch(
            "app.rag.services.product_sync.upsert_knowledge_chunk",
        ) as upsert,
    ):
        result = sync_product_knowledge_batch(
            mysql_db,
            rag_db,
            provider,
        )

    assert result == (0, None)
    provider.embed_documents.assert_not_called()
    upsert.assert_not_called()
    rag_db.commit.assert_not_called()


def test_sync_product_batch_rejects_embedding_count_mismatch() -> None:
    mysql_db = Mock(spec=Session)
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    provider.embed_documents.return_value = []

    with (
        patch(
            "app.rag.services.product_sync."
            "get_product_batch_for_knowledge_sync",
            return_value=[build_product()],
        ),
        patch(
            "app.rag.services.product_sync.upsert_knowledge_chunk",
        ) as upsert,
    ):
        with pytest.raises(
            RuntimeError,
            match="文档1条，向量0条",
        ):
            sync_product_knowledge_batch(
                mysql_db,
                rag_db,
                provider,
            )

    upsert.assert_not_called()
    rag_db.commit.assert_not_called()


def test_sync_product_batch_rolls_back_partial_writes() -> None:
    mysql_db = Mock(spec=Session)
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    products = [
        build_product(12),
        build_product(13),
    ]
    provider.embed_documents.return_value = [
        [0.1] * settings.rag_embedding_dimension,
        [0.2] * settings.rag_embedding_dimension,
    ]
    write_error = ValueError("第二条向量写入失败")

    with (
        patch(
            "app.rag.services.product_sync."
            "get_product_batch_for_knowledge_sync",
            return_value=products,
        ),
        patch(
            "app.rag.services.product_sync.upsert_knowledge_chunk",
            side_effect=[object(), write_error],
        ) as upsert,
    ):
        with pytest.raises(ValueError) as error_info:
            sync_product_knowledge_batch(
                mysql_db,
                rag_db,
                provider,
            )

    assert error_info.value is write_error
    assert upsert.call_count == 2
    rag_db.rollback.assert_called_once_with()
    rag_db.commit.assert_not_called()
