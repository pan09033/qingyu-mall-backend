from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.rag import (
    PolicyKnowledgeDocument,
    PolicyKnowledgeMetadata,
    ProductKnowledgeDocument,
    ProductKnowledgeMetadata,
    RagAnswerResponse,
    RagPolicyRebuildResponse,
    RagProductSyncResponse,
    RagQuestionRequest,
    RagSourceResponse,
)


def test_product_knowledge_document_builds_stable_key() -> None:
    document = ProductKnowledgeDocument(
        source_id="15",
        title="静音降噪蓝牙耳机",
        content=(
            "商品名称：静音降噪蓝牙耳机。"
            "分类：耳机。适合办公室和通勤使用。"
        ),
        metadata=ProductKnowledgeMetadata(
            product_id=15,
            category_id=3,
            category_name="耳机",
            price=Decimal("399.00"),
            stock=8,
        ),
    )

    assert document.document_key == "product:15:0"
    assert document.metadata.price == Decimal("399.00")


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("price", Decimal("0")),
        ("stock", -1),
    ],
)
def test_product_knowledge_metadata_rejects_invalid_values(
    field_name: str,
    invalid_value: Decimal | int,
) -> None:
    values = {
        "product_id": 15,
        "category_id": 3,
        "category_name": "耳机",
        "price": Decimal("399.00"),
        "stock": 8,
    }
    values[field_name] = invalid_value

    with pytest.raises(ValidationError):
        ProductKnowledgeMetadata(**values)


def test_policy_knowledge_document_builds_stable_key() -> None:
    document = PolicyKnowledgeDocument(
        source_id="refund_policy",
        title="商城退款与退货规则 - 已发货订单",
        content=(
            "文档名称：商城退款与退货规则。"
            "章节：已发货订单。"
            "已发货订单需要申请退货退款。"
        ),
        chunk_index=2,
        metadata=PolicyKnowledgeMetadata(
            document_name="商城退款与退货规则",
            section="已发货订单",
            topic="refund",
            source_file="refund_policy.md",
        ),
    )

    assert document.document_key == "policy:refund_policy:2"
    assert document.metadata.section == "已发货订单"


def test_policy_metadata_rejects_blank_section() -> None:
    with pytest.raises(ValidationError):
        PolicyKnowledgeMetadata(
            document_name="商城退款与退货规则",
            section="",
            topic="refund",
            source_file="refund_policy.md",
        )


def test_rag_question_request_accepts_normal_question() -> None:
    request = RagQuestionRequest(
        question="预算500元以内，有什么耳机推荐？",
    )

    assert request.question == "预算500元以内，有什么耳机推荐？"


@pytest.mark.parametrize(
    "question",
    [
        "",
        "问" * 501,
    ],
)
def test_rag_question_request_rejects_invalid_length(
    question: str,
) -> None:
    with pytest.raises(ValidationError):
        RagQuestionRequest(question=question)


def test_rag_answer_response_contains_source() -> None:
    response = RagAnswerResponse(
        answer="已发货订单需要申请退货退款。",
        sources=[
            RagSourceResponse(
                citation_number=1,
                source_type="policy",
                source_id="refund_policy",
                title="商城退款与退货规则 - 已发货订单",
            ),
        ],
    )

    assert response.sources[0].source_type == "policy"
    assert response.sources[0].source_id == "refund_policy"


def test_rag_answer_responses_have_independent_source_lists() -> None:
    first = RagAnswerResponse(answer="第一个回答")
    second = RagAnswerResponse(answer="第二个回答")

    first.sources.append(
        RagSourceResponse(
            citation_number=1,
            source_type="product",
            source_id="15",
            title="静音降噪蓝牙耳机",
        )
    )

    assert len(first.sources) == 1
    assert second.sources == []


def test_policy_rebuild_response_contains_sync_result() -> None:
    response = RagPolicyRebuildResponse(
        source_id="shipping_policy",
        topic="shipping",
        synced_chunk_count=5,
    )
    # response：管理员重建规则知识后的响应

    assert response.model_dump() == {
        "source_id": "shipping_policy",
        "topic": "shipping",
        "synced_chunk_count": 5,
    }


def test_policy_rebuild_response_rejects_unknown_topic() -> None:
    with pytest.raises(ValidationError):
        RagPolicyRebuildResponse(
            source_id="holiday_policy",
            topic="holiday",
            synced_chunk_count=1,
        )


def test_product_sync_response_contains_batch_cursor() -> None:
    response = RagProductSyncResponse(
        synced_product_count=100,
        next_after_id=125,
    )
    # response：商品批量同步接口响应

    assert response.model_dump() == {
        "synced_product_count": 100,
        "next_after_id": 125,
    }


def test_product_sync_response_allows_completed_cursor() -> None:
    response = RagProductSyncResponse(
        synced_product_count=0,
        next_after_id=None,
    )

    assert response.next_after_id is None


@pytest.mark.parametrize(
    ("synced_product_count", "next_after_id"),
    [
        (-1, None),
        (1, 0),
    ],
)
def test_product_sync_response_rejects_invalid_values(
    synced_product_count: int,
    next_after_id: int | None,
) -> None:
    with pytest.raises(ValidationError):
        RagProductSyncResponse(
            synced_product_count=synced_product_count,
            next_after_id=next_after_id,
        )
