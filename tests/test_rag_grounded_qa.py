import json
from unittest.mock import Mock, patch

import pytest

from app.rag.services.grounded_qa import answer_supported_question, validate_grounded_answer
from app.rag.models.knowledge_chunk import KnowledgeChunk


@pytest.fixture
def matches():
    return [(KnowledgeChunk(source_type="policy", source_id="shipping_policy", title="收货地址规则",
                            content="订单支付后不能继续修改收货地址。"), 0.718)]


def test_supported_answer_shows_verified_excerpt(matches):
    result = validate_grounded_answer(json.dumps({"supported": True,
        "answer": "支付后不能修改收货地址。[资料1]",
        "evidence": [{"citation_number": 1, "quote": "订单支付后不能继续修改收货地址。"}]}), matches)
    assert result.kind == "knowledge"
    assert result.sources[0].excerpt == "订单支付后不能继续修改收货地址。"


@pytest.mark.parametrize("payload", [
    "不是JSON", "[]", '{"supported":false,"answer":"","evidence":[]}',
    '{"supported":true,"answer":"能开票[资料1]","evidence":[]}',
    '{"supported":true,"answer":"可以修改[资料1]","evidence":[{"citation_number":1,"quote":"随时都可以修改"}]}',
    '{"supported":true,"answer":"不能修改[资料2]","evidence":[{"citation_number":1,"quote":"订单支付后不能继续修改收货地址。"}]}',
    '{"supported":true,"answer":"没有标注","evidence":[{"citation_number":1,"quote":"订单支付后不能继续修改收货地址。"}]}',
    '{"supported":true,"answer":"不能修改[资料2]","evidence":[{"citation_number":2,"quote":"订单支付后不能继续修改收货地址。"}]}',
])
def test_missing_or_fabricated_evidence_falls_back_to_handoff(payload, matches):
    result = validate_grounded_answer(payload, matches)
    assert result.kind == "no_knowledge"
    assert result.sources == []
    assert result.handoff_available


def test_empty_retrieval_does_not_load_chat():
    embedding, chat = Mock(), Mock()
    with patch("app.rag.services.grounded_qa.retrieve_knowledge", return_value=[]):
        result = answer_supported_question(Mock(), "商城支持开发票吗", embedding, chat, 0.5, 5)
    assert result.kind == "no_knowledge"
    chat.assert_not_called()


def test_invoice_question_cannot_use_shipping_evidence(matches):
    embedding, chat = Mock(), Mock()
    with patch("app.rag.services.grounded_qa.retrieve_knowledge", return_value=matches):
        result = answer_supported_question(Mock(), "商城能开发票吗", embedding, chat, 0.5, 5)
    assert result.kind == "no_knowledge"
    chat.assert_not_called()
