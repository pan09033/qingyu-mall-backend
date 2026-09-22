from pathlib import Path

import pytest

from app.rag.ingestion.policy import (
    build_policy_knowledge_documents,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_policy(
    tmp_path: Path,
    content: str,
) -> Path:
    file_path = tmp_path / "refund_policy.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_policy_markdown_is_split_by_second_level_heading(
    tmp_path: Path,
) -> None:
    file_path = write_policy(
        tmp_path,
        (
            "# 商城退款规则\n\n"
            "## 未发货订单\n\n"
            "已付款未发货时可以申请仅退款。\n\n"
            "## 已发货订单\n\n"
            "已发货时需要申请退货退款。\n"
        ),
    )

    documents = build_policy_knowledge_documents(
        file_path,
        source_id="refund_policy",
        topic="refund",
    )

    assert len(documents) == 2
    assert documents[0].document_key == "policy:refund_policy:0"
    assert documents[1].document_key == "policy:refund_policy:1"
    assert documents[1].title == "商城退款规则 - 已发货订单"
    assert documents[1].content.startswith(
        "文档名称：商城退款规则。\n"
        "章节：已发货订单。\n"
    )
    assert documents[1].metadata.section == "已发货订单"
    assert documents[1].metadata.topic == "refund"
    assert documents[1].metadata.source_file == "refund_policy.md"


def test_payment_policy_document_can_be_parsed() -> None:
    file_path = (
        PROJECT_ROOT
        / "knowledge"
        / "policies"
        / "payment_policy.md"
    )

    documents = build_policy_knowledge_documents(
        file_path,
        source_id="payment_policy",
        topic="payment",
    )

    assert len(documents) == 5
    assert documents[0].document_key == (
        "policy:payment_policy:0"
    )
    assert documents[-1].document_key == (
        "policy:payment_policy:4"
    )
    assert [
        document.metadata.section
        for document in documents
    ] == [
        "可以支付的订单",
        "支付金额和支付记录",
        "支付成功后的状态",
        "支付记录查询",
        "支付方式说明",
    ]
    assert all(
        document.metadata.topic == "payment"
        for document in documents
    )
    assert all(
        document.metadata.source_file == "payment_policy.md"
        for document in documents
    )
    assert "不能自行编造支付渠道" in documents[-1].content


def test_shipping_policy_document_can_be_parsed() -> None:
    file_path = (
        PROJECT_ROOT
        / "knowledge"
        / "policies"
        / "shipping_policy.md"
    )

    documents = build_policy_knowledge_documents(
        file_path,
        source_id="shipping_policy",
        topic="shipping",
    )

    assert len(documents) == 5
    assert documents[0].document_key == (
        "policy:shipping_policy:0"
    )
    assert documents[-1].document_key == (
        "policy:shipping_policy:4"
    )
    assert [
        document.metadata.section
        for document in documents
    ] == [
        "订单发货条件",
        "订单状态流转",
        "确认完成",
        "修改收货地址",
        "配送信息说明",
    ]
    assert all(
        document.metadata.topic == "shipping"
        for document in documents
    )
    assert all(
        document.metadata.source_file == "shipping_policy.md"
        for document in documents
    )
    assert "不能自行编造" in documents[-1].content


def test_policy_markdown_requires_first_level_heading(
    tmp_path: Path,
) -> None:
    file_path = write_policy(
        tmp_path,
        "## 退款条件\n\n已付款后可以申请。\n",
    )

    with pytest.raises(
        ValueError,
        match="缺少一级标题",
    ):
        build_policy_knowledge_documents(
            file_path,
            source_id="refund_policy",
            topic="refund",
        )


def test_policy_markdown_requires_second_level_heading(
    tmp_path: Path,
) -> None:
    file_path = write_policy(
        tmp_path,
        "# 商城退款规则\n\n只有普通正文。\n",
    )

    with pytest.raises(
        ValueError,
        match="缺少二级标题",
    ):
        build_policy_knowledge_documents(
            file_path,
            source_id="refund_policy",
            topic="refund",
        )


def test_policy_markdown_rejects_empty_section(
    tmp_path: Path,
) -> None:
    file_path = write_policy(
        tmp_path,
        (
            "# 商城退款规则\n\n"
            "## 退款条件\n\n"
            "## 退款流程\n\n"
            "等待管理员审核。\n"
        ),
    )

    with pytest.raises(
        ValueError,
        match="章节没有正文：退款条件",
    ):
        build_policy_knowledge_documents(
            file_path,
            source_id="refund_policy",
            topic="refund",
        )
