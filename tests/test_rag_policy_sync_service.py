from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.rag.providers.embedding import (
    LocalBgeEmbeddingProvider,
)
from app.rag.services.policy_sync import (
    POLICY_DIRECTORY,
    rebuild_policy_knowledge_by_topic,
    sync_policy_knowledge,
)
from app.schemas.rag import (
    PolicyKnowledgeDocument,
    PolicyKnowledgeMetadata,
)


def build_policy_documents() -> list[PolicyKnowledgeDocument]:
    return [
        PolicyKnowledgeDocument(
            source_id="refund_policy",
            title=f"商城退款规则 - {section}",
            content=f"章节：{section}。{body}",
            chunk_index=index,
            metadata=PolicyKnowledgeMetadata(
                document_name="商城退款规则",
                section=section,
                topic="refund",
                source_file="refund_policy.md",
            ),
        )
        for index, (section, body) in enumerate(
            [
                ("未发货订单", "可以申请仅退款。"),
                ("已发货订单", "需要申请退货退款。"),
            ]
        )
    ]


def test_policy_sync_runs_all_steps_in_one_transaction() -> None:
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    documents = build_policy_documents()
    embeddings = [
        [0.1] * settings.rag_embedding_dimension,
        [0.2] * settings.rag_embedding_dimension,
    ]
    events: list[str] = []

    def embed_documents(texts: list[str]) -> list[list[float]]:
        events.append("embed")
        assert texts == [document.content for document in documents]
        return embeddings

    provider.embed_documents.side_effect = embed_documents
    rag_db.commit.side_effect = lambda: events.append("commit")

    with (
        patch(
            "app.rag.services.policy_sync."
            "build_policy_knowledge_documents",
            return_value=documents,
        ) as build_documents,
        patch(
            "app.rag.services.policy_sync.upsert_knowledge_chunk",
            side_effect=lambda *args: events.append("upsert"),
        ) as upsert,
        patch(
            "app.rag.services.policy_sync."
            "delete_stale_knowledge_chunks",
            side_effect=lambda *args, **kwargs: events.append(
                "delete_stale"
            ),
        ) as delete_stale,
    ):
        count = sync_policy_knowledge(
            rag_db,
            provider,
            Path("refund_policy.md"),
            source_id="refund_policy",
            topic="refund",
        )

    build_documents.assert_called_once_with(
        Path("refund_policy.md"),
        source_id="refund_policy",
        topic="refund",
    )
    assert upsert.call_count == 2
    assert upsert.call_args_list[0].args[2] is embeddings[0]
    assert upsert.call_args_list[1].args[2] is embeddings[1]
    delete_stale.assert_called_once_with(
        rag_db,
        source_type="policy",
        source_id="refund_policy",
        active_document_keys={
            "policy:refund_policy:0",
            "policy:refund_policy:1",
        },
    )
    assert events == [
        "embed",
        "upsert",
        "upsert",
        "delete_stale",
        "commit",
    ]
    assert count == 2
    rag_db.rollback.assert_not_called()


def test_policy_sync_rejects_embedding_count_mismatch() -> None:
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    provider.embed_documents.return_value = [
        [0.1] * settings.rag_embedding_dimension
    ]

    with (
        patch(
            "app.rag.services.policy_sync."
            "build_policy_knowledge_documents",
            return_value=build_policy_documents(),
        ),
        patch(
            "app.rag.services.policy_sync.upsert_knowledge_chunk",
        ) as upsert,
        patch(
            "app.rag.services.policy_sync."
            "delete_stale_knowledge_chunks",
        ) as delete_stale,
    ):
        with pytest.raises(
            RuntimeError,
            match="文档2条，向量1条",
        ):
            sync_policy_knowledge(
                rag_db,
                provider,
                Path("refund_policy.md"),
                source_id="refund_policy",
                topic="refund",
            )

    upsert.assert_not_called()
    delete_stale.assert_not_called()
    rag_db.commit.assert_not_called()


def test_policy_sync_rolls_back_when_cleanup_fails() -> None:
    rag_db = Mock(spec=Session)
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    provider.embed_documents.return_value = [
        [0.1] * settings.rag_embedding_dimension,
        [0.2] * settings.rag_embedding_dimension,
    ]
    cleanup_error = RuntimeError("旧分段清理失败")

    with (
        patch(
            "app.rag.services.policy_sync."
            "build_policy_knowledge_documents",
            return_value=build_policy_documents(),
        ),
        patch(
            "app.rag.services.policy_sync.upsert_knowledge_chunk",
        ) as upsert,
        patch(
            "app.rag.services.policy_sync."
            "delete_stale_knowledge_chunks",
            side_effect=cleanup_error,
        ),
    ):
        with pytest.raises(RuntimeError) as error_info:
            sync_policy_knowledge(
                rag_db,
                provider,
                Path("refund_policy.md"),
                source_id="refund_policy",
                topic="refund",
            )

    assert error_info.value is cleanup_error
    assert upsert.call_count == 2
    rag_db.rollback.assert_called_once_with()
    rag_db.commit.assert_not_called()


def test_rebuild_policy_by_topic_uses_fixed_source() -> None:
    rag_db = Mock(spec=Session)
    # rag_db：模拟RAG数据库会话
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    # provider：模拟BGE Provider

    with patch(
        "app.rag.services.policy_sync.sync_policy_knowledge",
        return_value=5,
    ) as sync_policy:
        # sync_policy：模拟已有的规则同步函数
        result = rebuild_policy_knowledge_by_topic(
            rag_db=rag_db,
            embedding_provider=provider,
            topic=" SHIPPING ",
        )
        # result：来源ID和同步数量

    sync_policy.assert_called_once_with(
        rag_db=rag_db,
        embedding_provider=provider,
        file_path=(
            POLICY_DIRECTORY / "shipping_policy.md"
        ),
        source_id="shipping_policy",
        topic="shipping",
    )
    assert result == ("shipping_policy", 5)


def test_rebuild_policy_rejects_unknown_topic() -> None:
    rag_db = Mock(spec=Session)
    # rag_db：模拟RAG数据库会话
    provider = Mock(spec=LocalBgeEmbeddingProvider)
    # provider：模拟BGE Provider

    with patch(
        "app.rag.services.policy_sync.sync_policy_knowledge",
    ) as sync_policy:
        # sync_policy：模拟已有的规则同步函数
        with pytest.raises(
            ValueError,
            match="不支持的规则主题：unknown",
        ):
            rebuild_policy_knowledge_by_topic(
                rag_db=rag_db,
                embedding_provider=provider,
                topic=" unknown ",
            )

    sync_policy.assert_not_called()
    assert provider.mock_calls == []
    assert rag_db.mock_calls == []
