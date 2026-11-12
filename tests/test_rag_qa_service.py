from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.rag.exceptions import RagServiceUnavailableError
from app.rag.models.knowledge_chunk import KnowledgeChunk
from app.rag.providers.chat import (
    ChatProviderUnavailableError,
    DeepSeekChatProvider,
)
from app.rag.providers.embedding import LocalBgeEmbeddingProvider
from app.rag.services.qa import (
    NO_RELIABLE_KNOWLEDGE_ANSWER,
    PERSONAL_REFUND_STATUS_ANSWER,
    SYSTEM_PROMPT,
    answer_question,
    build_cited_sources,
    build_user_prompt,
)


def build_chunk(
    source_type: str,
    source_id: str,
    title: str,
    content: str,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        document_key=f"{source_type}:{source_id}:0",
        source_type=source_type,
        source_id=source_id,
        title=title,
        content=content,
        chunk_index=0,
        metadata_json={},
        embedding=[0.0] * 512,
    )


def test_system_prompt_requires_grounded_answer() -> None:
    assert "只能根据用户消息中提供的商城资料回答" in SYSTEM_PROMPT
    assert "不得编造" in SYSTEM_PROMPT
    assert "资料不足" in SYSTEM_PROMPT


def test_build_user_prompt_numbers_knowledge_in_order() -> None:
    policy_chunk = build_chunk(
        source_type="policy",
        source_id="refund_policy",
        title="商城退款规则 - 已发货订单",
        content="已发货订单需要申请退货退款。",
    )
    product_chunk = build_chunk(
        source_type="product",
        source_id="15",
        title="静音降噪蓝牙耳机",
        content="商品价格399元，适合办公室使用。",
    )
    product_chunk.metadata_json = {
        "price": "399.00",
        "stock": 8,
    }

    prompt = build_user_prompt(
        "已经发货怎样退款？",
        [
            (policy_chunk, 0.75),
            (product_chunk, 0.55),
        ],
    )

    assert prompt.startswith(
        "用户问题：已经发货怎样退款？"
    )
    assert (
        "[资料1]\n"
        "标题：商城退款规则 - 已发货订单\n"
        "来源类型：policy\n"
        "来源ID：refund_policy\n"
        "内容：已发货订单需要申请退货退款。"
    ) in prompt
    assert (
        "[资料2]\n"
        "标题：静音降噪蓝牙耳机\n"
        "来源类型：product\n"
        "来源ID：15\n"
        "内容：商品价格399元，适合办公室使用。\n"
        "商品价格：399.00元\n"
        "商品库存：8件"
    ) in prompt
    assert prompt.index("[资料1]") < prompt.index("[资料2]")


def test_build_cited_sources_keeps_valid_unique_citations() -> None:
    matches = [
        (
            build_chunk(
                "policy",
                "refund_policy",
                f"退款规则 - 章节{index}",
                f"退款规则内容{index}",
            ),
            0.80 - index / 100,
        )
        for index in range(1, 4)
    ]

    sources = build_cited_sources(
        "依据[资料3]处理，并满足[资料2]。[资料3][资料99]",
        matches,
    )

    assert [
        source.citation_number
        for source in sources
    ] == [3, 2]
    assert [source.title for source in sources] == [
        "退款规则 - 章节3",
        "退款规则 - 章节2",
    ]


def test_build_cited_sources_falls_back_to_all_matches() -> None:
    matches = [
        (
            build_chunk(
                "product",
                str(index),
                f"商品{index}",
                f"商品内容{index}",
            ),
            0.70,
        )
        for index in range(1, 3)
    ]

    sources = build_cited_sources(
        "根据商城资料，可以考虑这些商品。",
        matches,
    )

    assert [
        source.citation_number
        for source in sources
    ] == [1, 2]


def test_answer_question_skips_chat_when_no_knowledge() -> None:
    rag_db = Mock(spec=Session)
    embedding_provider = Mock(spec=LocalBgeEmbeddingProvider)
    chat_provider = Mock(spec=DeepSeekChatProvider)
    embedding_provider_factory = Mock(
        return_value=embedding_provider,
    )
    # embedding_provider_factory：模拟获取BGE的函数
    chat_provider_factory = Mock(
        return_value=chat_provider,
    )
    # chat_provider_factory：模拟获取大模型Provider的函数

    with patch(
        "app.rag.services.qa.retrieve_knowledge",
        return_value=[],
    ) as retrieve:
        response = answer_question(
            rag_db=rag_db,
            embedding_provider_factory=embedding_provider_factory,
            chat_provider_factory=chat_provider_factory,
            question="月球背面有什么商品？",
            minimum_similarity=0.50,
        )

    retrieve.assert_called_once_with(
        rag_db=rag_db,
        embedding_provider=embedding_provider,
        question="月球背面有什么商品？",
        minimum_similarity=0.50,
        source_type="product",
        topic=None,
        max_price=None,
        limit=5,
    )
    embedding_provider_factory.assert_called_once_with()
    chat_provider_factory.assert_not_called()
    chat_provider.generate_answer.assert_not_called()
    assert response.answer == NO_RELIABLE_KNOWLEDGE_ANSWER
    assert response.sources == []


@pytest.mark.parametrize(
    "question",
    ["我的退款到账了吗？", "我的退款到账了没？", "我的退款有没有到账？"],
)
def test_personal_refund_query_skips_retrieval_and_generation(
    question: str,  # question：用户问题
) -> None:
    rag_db = Mock(spec=Session)  # rag_db：模拟数据库会话
    embedding_provider = Mock(spec=LocalBgeEmbeddingProvider)
    # embedding_provider：模拟向量模型
    chat_provider = Mock(spec=DeepSeekChatProvider)
    # chat_provider：模拟大模型
    embedding_provider_factory = Mock(
        return_value=embedding_provider,
    )
    # embedding_provider_factory：模拟获取BGE的函数
    chat_provider_factory = Mock(
        return_value=chat_provider,
    )
    # chat_provider_factory：模拟获取大模型Provider的函数

    with patch("app.rag.services.qa.retrieve_knowledge") as retrieve:
        # retrieve：模拟检索函数
        response = answer_question(
            rag_db=rag_db,
            embedding_provider_factory=embedding_provider_factory,
            chat_provider_factory=chat_provider_factory,
            question=question,
            minimum_similarity=0.50,
        )
        # response：问答响应

    assert response.answer == PERSONAL_REFUND_STATUS_ANSWER
    assert response.sources == []
    retrieve.assert_not_called()
    embedding_provider_factory.assert_not_called()
    chat_provider_factory.assert_not_called()
    assert embedding_provider.mock_calls == []
    assert chat_provider.mock_calls == []
    assert rag_db.mock_calls == []


def test_answer_question_extracts_product_budget() -> None:
    rag_db = Mock(spec=Session)
    embedding_provider = Mock(spec=LocalBgeEmbeddingProvider)
    chat_provider = Mock(spec=DeepSeekChatProvider)

    with patch(
        "app.rag.services.qa.retrieve_knowledge",
        return_value=[],
    ) as retrieve:
        answer_question(
            rag_db=rag_db,
            embedding_provider_factory=lambda: embedding_provider,
            chat_provider_factory=lambda: chat_provider,
            question="预算500元以内，有什么耳机推荐？",
            minimum_similarity=0.50,
        )

    retrieve.assert_called_once_with(
        rag_db=rag_db,
        embedding_provider=embedding_provider,
        question="预算500元以内，有什么耳机推荐？",
        minimum_similarity=0.50,
        source_type="product",
        topic=None,
        max_price=Decimal("500"),
        limit=5,
    )
    chat_provider.generate_answer.assert_not_called()


@pytest.mark.parametrize(
    ("question", "expected_topic"),
    [
        ("退款需要满足什么条件？", "refund"),
        ("已经发货的订单怎样退款？", None),
        ("付款后还能修改收货地址吗？", None),
    ],
)
def test_answer_question_passes_policy_scope_to_retrieval(
    question: str,  # question：单主题或跨主题的规则问题
    expected_topic: str | None,  # expected_topic：预期主题限制
) -> None:
    rag_db = Mock(spec=Session)
    embedding_provider = Mock(spec=LocalBgeEmbeddingProvider)
    chat_provider = Mock(spec=DeepSeekChatProvider)

    with patch(
        "app.rag.services.qa.retrieve_knowledge",
        return_value=[],
    ) as retrieve:
        answer_question(
            rag_db=rag_db,
            embedding_provider_factory=lambda: embedding_provider,
            chat_provider_factory=lambda: chat_provider,
            question=question,
            minimum_similarity=0.50,
        )

    retrieve.assert_called_once_with(
        rag_db=rag_db,
        embedding_provider=embedding_provider,
        question=question,
        minimum_similarity=0.50,
        source_type="policy",
        topic=expected_topic,
        max_price=None,
        limit=5,
    )


@pytest.mark.parametrize(
    "question",
    ["  已经发货怎样退款？  ", "我的订单如何申请退款？"],
)
def test_answer_question_generates_answer_with_sources(
    question: str,  # question：公共退款规则问题
) -> None:
    rag_db = Mock(spec=Session)
    embedding_provider = Mock(spec=LocalBgeEmbeddingProvider)
    chat_provider = Mock(spec=DeepSeekChatProvider)
    chat_provider.generate_answer.return_value = (
        "已发货订单需要申请退货退款。[资料1]"
    )
    policy_chunk = build_chunk(
        source_type="policy",
        source_id="refund_policy",
        title="商城退款规则 - 已发货订单",
        content="已发货订单需要申请退货退款。",
    )

    with patch(
        "app.rag.services.qa.retrieve_knowledge",
        return_value=[(policy_chunk, 0.75)],
    ):
        response = answer_question(
            rag_db=rag_db,
            embedding_provider_factory=lambda: embedding_provider,
            chat_provider_factory=lambda: chat_provider,
            question=question,
            minimum_similarity=0.50,
            source_type="policy",
            topic="refund",
            limit=3,
        )

    expected_user_prompt = build_user_prompt(
        question.strip(),
        [(policy_chunk, 0.75)],
    )
    chat_provider.generate_answer.assert_called_once_with(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=expected_user_prompt,
    )
    assert response.answer == (
        "已发货订单需要申请退货退款。[资料1]"
    )
    assert len(response.sources) == 1
    assert response.sources[0].citation_number == 1
    assert response.sources[0].source_type == "policy"
    assert response.sources[0].source_id == "refund_policy"


def test_answer_question_translates_chat_provider_failure() -> None:
    rag_db = Mock(spec=Session)
    embedding_provider = Mock(spec=LocalBgeEmbeddingProvider)
    chat_provider = Mock(spec=DeepSeekChatProvider)
    chat_provider.generate_answer.side_effect = (
        ChatProviderUnavailableError(
            "DeepSeek服务响应超时"
        )
    )
    policy_chunk = build_chunk(
        source_type="policy",
        source_id="refund_policy",
        title="商城退款规则 - 已发货订单",
        content="已发货订单需要申请退货退款。",
    )

    with patch(
        "app.rag.services.qa.retrieve_knowledge",
        return_value=[(policy_chunk, 0.75)],
    ):
        with pytest.raises(
            RagServiceUnavailableError,
        ) as error_info:
            answer_question(
                rag_db=rag_db,
                embedding_provider_factory=lambda: embedding_provider,
                chat_provider_factory=lambda: chat_provider,
                question="已经发货怎样退款？",
                minimum_similarity=0.50,
            )

    assert error_info.value.status_code == 503
    assert error_info.value.detail == (
        "智能购物助手暂时不可用，请稍后重试"
    )


def test_answer_question_translates_embedding_load_failure() -> None:
    # embedding_factory：模拟本地模型文件缺失
    def unavailable_embedding() -> LocalBgeEmbeddingProvider:
        raise RuntimeError("local model unavailable")

    with pytest.raises(RagServiceUnavailableError) as caught:
        answer_question(
            rag_db=Mock(spec=Session),
            embedding_provider_factory=unavailable_embedding,
            chat_provider_factory=lambda: Mock(spec=DeepSeekChatProvider),
            question="有什么耳机推荐？",
            minimum_similarity=0.50,
        )
    assert caught.value.status_code == 503
    assert "local model unavailable" not in caught.value.detail


def test_answer_question_translates_retrieval_database_failure() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    with patch(
        "app.rag.services.qa.retrieve_knowledge",
        side_effect=SQLAlchemyError("database unavailable"),
    ):
        with pytest.raises(RagServiceUnavailableError) as caught:
            answer_question(
                rag_db=Mock(spec=Session),
                embedding_provider_factory=lambda: Mock(spec=LocalBgeEmbeddingProvider),
                chat_provider_factory=lambda: Mock(spec=DeepSeekChatProvider),
                question="有什么耳机推荐？",
                minimum_similarity=0.50,
            )
    assert caught.value.status_code == 503
    assert "database unavailable" not in caught.value.detail


def test_answer_question_translates_chat_provider_creation_failure() -> None:
    def unavailable_chat() -> DeepSeekChatProvider:
        raise ValueError("missing API configuration")

    chunk = build_chunk(
        source_type="policy",
        source_id="refund_policy",
        title="退款规则",
        content="申请退款的说明。",
    )
    with patch(
        "app.rag.services.qa.retrieve_knowledge",
        return_value=[(chunk, 0.75)],
    ):
        with pytest.raises(RagServiceUnavailableError) as caught:
            answer_question(
                rag_db=Mock(spec=Session),
                embedding_provider_factory=lambda: Mock(spec=LocalBgeEmbeddingProvider),
                chat_provider_factory=unavailable_chat,
                question="怎样申请退款？",
                minimum_similarity=0.50,
            )
    assert caught.value.status_code == 503
    assert "missing API configuration" not in caught.value.detail
