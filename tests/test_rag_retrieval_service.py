from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.rag.providers.embedding import (
    LocalBgeEmbeddingProvider,
)
from app.rag.services.retrieval import (
    retrieve_knowledge,
)


def test_retrieval_embeds_normalized_question_and_filters() -> None:
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    query_embedding = [
        0.1
    ] * settings.rag_embedding_dimension
    provider.embed_query.return_value = query_embedding
    accepted_chunk = object()
    rejected_chunk = object()

    with patch(
        "app.rag.services.retrieval.search_knowledge",
        return_value=[
            (accepted_chunk, 0.72),
            (rejected_chunk, 0.49),
        ],
    ) as search:
        results = retrieve_knowledge(
            rag_db,
            provider,
            "  预算500元以内，有什么耳机推荐？  ",
            minimum_similarity=0.50,
            source_type="product",
            max_price=Decimal("500.00"),
            limit=3,
        )

    provider.embed_query.assert_called_once_with(
        "预算500元以内，有什么耳机推荐？"
    )
    search.assert_called_once_with(
        rag_db,
        query_embedding=query_embedding,
        source_type="product",
        topic=None,
        max_price=Decimal("500.00"),
        limit=3,
    )
    assert results == [(accepted_chunk, 0.72)]


def test_retrieval_forwards_policy_topic_filter() -> None:
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    query_embedding = [
        0.1
    ] * settings.rag_embedding_dimension
    provider.embed_query.return_value = query_embedding

    with patch(
        "app.rag.services.retrieval.search_knowledge",
        return_value=[],
    ) as search:
        results = retrieve_knowledge(
            rag_db,
            provider,
            "已经发货的订单怎样退款？",
            minimum_similarity=0.50,
            source_type="policy",
            topic="refund",
            limit=3,
        )

    search.assert_called_once_with(
        rag_db,
        query_embedding=query_embedding,
        source_type="policy",
        topic="refund",
        max_price=None,
        limit=3,
    )
    assert results == []


def test_retrieval_returns_empty_when_all_candidates_are_weak() -> None:
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    provider.embed_query.return_value = [
        0.1
    ] * settings.rag_embedding_dimension

    with patch(
        "app.rag.services.retrieval.search_knowledge",
        return_value=[
            (object(), 0.40),
            (object(), 0.25),
        ],
    ):
        results = retrieve_knowledge(
            rag_db,
            provider,
            "月球背面有哪些地质结构？",
            minimum_similarity=0.50,
        )

    assert results == []


def test_retrieval_rejects_blank_question() -> None:
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)

    with pytest.raises(
        ValueError,
        match="用户问题不能为空",
    ):
        retrieve_knowledge(
            rag_db,
            provider,
            "   ",
            minimum_similarity=0.50,
        )

    provider.embed_query.assert_not_called()


@pytest.mark.parametrize(
    "minimum_similarity",
    [-1.01, 1.01],
)
def test_retrieval_rejects_invalid_similarity_threshold(
    minimum_similarity: float,
) -> None:
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)

    with pytest.raises(
        ValueError,
        match="最低相似度必须在-1到1之间",
    ):
        retrieve_knowledge(
            rag_db,
            provider,
            "耳机推荐",
            minimum_similarity=minimum_similarity,
        )

    provider.embed_query.assert_not_called()
