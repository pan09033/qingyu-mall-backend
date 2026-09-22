from decimal import Decimal

import pytest

from app.rag.services.query_analysis import (
    extract_max_price,
    infer_knowledge_scope,
    is_personal_refund_status_query,
)


@pytest.mark.parametrize(
    ("question", "expected_price"),
    [
        (
            "预算500元以内，有什么耳机推荐？",
            Decimal("500"),
        ),
        (
            "最多399.50元的键盘",
            Decimal("399.50"),
        ),
        (
            "500元以下有什么商品？",
            Decimal("500"),
        ),
    ],
)
def test_extract_max_price_supports_budget_expressions(
    question: str,
    expected_price: Decimal,
) -> None:
    assert extract_max_price(question) == expected_price


@pytest.mark.parametrize(
    "question",
    [
        "有什么适合办公的耳机？",
        "这个商品价格是500元",
        "预算0元的商品",
    ],
)
def test_extract_max_price_returns_none_without_valid_budget(
    question: str,
) -> None:
    assert extract_max_price(question) is None


@pytest.mark.parametrize(
    ("question", "expected_scope"),
    [
        (
            "已经发货的订单怎样退款？",
            ("policy", "refund"),
        ),
        (
            "商城支持哪些支付方式？",
            ("policy", "payment"),
        ),
        (
            "订单什么时候发货？",
            ("policy", "shipping"),
        ),
        (
            "有什么适合办公的商品？",
            ("product", None),
        ),
        (
            "机械键盘和普通键盘有什么区别？",
            (None, None),
        ),
    ],
)
def test_infer_knowledge_scope(
    question: str,
    expected_scope: tuple[str | None, str | None],
) -> None:
    assert infer_knowledge_scope(question) == expected_scope


@pytest.mark.parametrize(
    "question",
    [
        "我的退款到账了吗？",
        "请问我的退款到账了没？",
        "帮我看看我的退款有没有到账",
        "  我的 退款\n到账了吗？  ",
    ],
)
def test_personal_refund_arrival_query_is_recognized(
    question: str,  # question：用户问题
) -> None:
    assert is_personal_refund_status_query(question) is True


@pytest.mark.parametrize(
    "question",
    [
        "退款需要满足什么条件？",
        "已发货的订单如何申请退款？",
        "我的订单如何申请退款？",
        "我的退款一般多久能到账？",
        "我的订单发货了吗？",
        "",
    ],
)
def test_other_questions_do_not_match_refund_arrival_query(
    question: str,  # question：用户问题
) -> None:
    assert is_personal_refund_status_query(question) is False
