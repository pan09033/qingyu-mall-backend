from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.config import settings
from app.rag.repositories.knowledge_chunk import (
    delete_stale_knowledge_chunks,
    search_knowledge,
    upsert_knowledge_chunk,
)
from app.schemas.rag import (
    PolicyKnowledgeDocument,
    PolicyKnowledgeMetadata,
    ProductKnowledgeDocument,
    ProductKnowledgeMetadata,
)


def build_document(
    price: Decimal = Decimal("399.00"),
) -> ProductKnowledgeDocument:
    return ProductKnowledgeDocument(
        source_id="12",
        title="静音降噪蓝牙耳机",
        content="商品名称：静音降噪蓝牙耳机。",
        metadata=ProductKnowledgeMetadata(
            product_id=12,
            category_id=3,
            category_name="耳机",
            price=price,
            stock=10,
        ),
    )


def test_upsert_rejects_wrong_embedding_dimension() -> None:
    db = Mock(spec=Session)
    embedding = [0.0] * (
        settings.rag_embedding_dimension - 1
    )

    with pytest.raises(
        ValueError,
        match="Embedding维度不匹配",
    ):
        upsert_knowledge_chunk(
            db,
            build_document(),
            embedding,
        )

    db.scalars.assert_not_called()


def test_upsert_builds_postgresql_conflict_update() -> None:
    db = Mock(spec=Session)
    expected_chunk = object()
    scalar_result = Mock()
    scalar_result.one.return_value = expected_chunk
    db.scalars.return_value = scalar_result

    result = upsert_knowledge_chunk(
        db,
        build_document(),
        [0.0] * settings.rag_embedding_dimension,
    )

    statement = db.scalars.call_args.args[0]
    compiled_sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
        )
    )

    assert "ON CONFLICT (document_key) DO UPDATE" in compiled_sql
    assert "RETURNING knowledge_chunks" in compiled_sql
    assert result is expected_chunk
    scalar_result.one.assert_called_once_with()


def test_upsert_accepts_policy_knowledge_document() -> None:
    db = Mock(spec=Session)
    scalar_result = Mock()
    scalar_result.one.return_value = object()
    db.scalars.return_value = scalar_result
    document = PolicyKnowledgeDocument(
        source_id="refund_policy",
        title="商城退款与退货规则 - 已发货订单",
        content="已发货订单需要申请退货退款。",
        chunk_index=2,
        metadata=PolicyKnowledgeMetadata(
            document_name="商城退款与退货规则",
            section="已发货订单",
            topic="refund",
            source_file="refund_policy.md",
        ),
    )

    upsert_knowledge_chunk(
        db,
        document,
        [0.0] * settings.rag_embedding_dimension,
    )

    statement = db.scalars.call_args.args[0]
    compiled = statement.compile(
        dialect=postgresql.dialect(),
    )

    assert "policy" in compiled.params.values()
    assert "refund_policy" in compiled.params.values()


def test_search_rejects_wrong_query_embedding_dimension() -> None:
    db = Mock(spec=Session)

    with pytest.raises(
        ValueError,
        match="问题Embedding维度不匹配",
    ):
        search_knowledge(
            db,
            [0.0] * (settings.rag_embedding_dimension - 1),
        )

    db.execute.assert_not_called()


def test_search_rejects_nonpositive_limit() -> None:
    db = Mock(spec=Session)

    with pytest.raises(
        ValueError,
        match="检索数量必须大于0",
    ):
        search_knowledge(
            db,
            [0.0] * settings.rag_embedding_dimension,
            limit=0,
        )

    db.execute.assert_not_called()


def test_search_builds_cosine_query_with_budget_filter() -> None:
    db = Mock(spec=Session)
    expected_chunk = object()
    execute_result = Mock()
    execute_result.all.return_value = [
        (expected_chunk, Decimal("0.75")),
    ]
    db.execute.return_value = execute_result

    matches = search_knowledge(
        db,
        [0.0] * settings.rag_embedding_dimension,
        source_type="product",
        max_price=Decimal("500.00"),
        limit=3,
    )

    statement = db.execute.call_args.args[0]
    compiled = statement.compile(
        dialect=postgresql.dialect(),
    )
    compiled_sql = str(compiled)

    assert "<=>" in compiled_sql
    assert "ORDER BY" in compiled_sql
    assert "CAST" in compiled_sql
    assert "NUMERIC(10, 2)" in compiled_sql
    assert Decimal("500.00") in compiled.params.values()
    assert matches == [(expected_chunk, 0.75)]


def test_search_builds_policy_topic_filter() -> None:
    db = Mock(spec=Session)
    execute_result = Mock()
    execute_result.all.return_value = []
    db.execute.return_value = execute_result

    search_knowledge(
        db,
        [0.0] * settings.rag_embedding_dimension,
        source_type="policy",
        topic=" refund ",
        limit=3,
    )

    statement = db.execute.call_args.args[0]
    compiled = statement.compile(
        dialect=postgresql.dialect(),
    )

    assert "topic" in compiled.params.values()
    assert "refund" in compiled.params.values()
    assert "policy" in compiled.params.values()


@pytest.mark.parametrize(
    ("source_type", "topic", "error_message"),
    [
        ("product", "refund", "规则主题过滤只能用于规则知识"),
        (None, "refund", "规则主题过滤只能用于规则知识"),
        ("policy", "   ", "规则主题不能为空"),
    ],
)
def test_search_rejects_invalid_topic_filter(
    source_type: str | None,
    topic: str,
    error_message: str,
) -> None:
    db = Mock(spec=Session)

    with pytest.raises(ValueError, match=error_message):
        search_knowledge(
            db,
            [0.0] * settings.rag_embedding_dimension,
            source_type=source_type,
            topic=topic,
        )

    db.execute.assert_not_called()


def test_delete_stale_chunks_keeps_active_document_keys() -> None:
    db = Mock(spec=Session)

    delete_stale_knowledge_chunks(
        db,
        source_type=" policy ",
        source_id=" refund_policy ",
        active_document_keys={
            "policy:refund_policy:0",
            "policy:refund_policy:1",
        },
    )

    statement = db.execute.call_args.args[0]
    compiled_sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True,
            },
        )
    )

    assert "DELETE FROM knowledge_chunks" in compiled_sql
    assert "source_type = 'policy'" in compiled_sql
    assert "source_id = 'refund_policy'" in compiled_sql
    assert "document_key NOT IN" in compiled_sql
    assert "policy:refund_policy:0" in compiled_sql
    assert "policy:refund_policy:1" in compiled_sql


def test_delete_with_empty_keys_still_limits_source() -> None:
    db = Mock(spec=Session)

    delete_stale_knowledge_chunks(
        db,
        source_type="policy",
        source_id="refund_policy",
        active_document_keys=set(),
    )

    statement = db.execute.call_args.args[0]
    compiled_sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True,
            },
        )
    )

    assert "source_type = 'policy'" in compiled_sql
    assert "source_id = 'refund_policy'" in compiled_sql
    assert "document_key NOT IN" not in compiled_sql


@pytest.mark.parametrize(
    ("source_type", "source_id"),
    [
        ("", "refund_policy"),
        ("policy", "   "),
    ],
)
def test_delete_stale_chunks_rejects_blank_source(
    source_type: str,
    source_id: str,
) -> None:
    db = Mock(spec=Session)

    with pytest.raises(ValueError):
        delete_stale_knowledge_chunks(
            db,
            source_type=source_type,
            source_id=source_id,
            active_document_keys=set(),
        )

    db.execute.assert_not_called()
