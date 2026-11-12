import re
from decimal import Decimal
from typing import Literal


BUDGET_PATTERNS = (
    re.compile(
        r"预算\s*(\d+(?:\.\d{1,2})?)\s*元"
        r"(?:以内|以下)?"
    ),
    re.compile(
        r"(?:不超过|最多)\s*"
        r"(\d+(?:\.\d{1,2})?)\s*元"
    ),
    re.compile(
        r"(\d+(?:\.\d{1,2})?)\s*元"
        r"(?:以内|以下)"
    ),
)

POLICY_TOPIC_KEYWORDS = (
    (
        "refund",
        ("退款", "退货", "售后"),
    ),
    (
        "payment",
        ("支付", "付款"),
    ),
    (
        "shipping",
        ("配送", "物流", "发货", "快递", "收货"),
    ),
)

PRODUCT_KEYWORDS = (
    "商品",
    "推荐",
    "价格",
    "预算",
    "库存",
    "适合",
)


def extract_max_price(
    question: str,
) -> Decimal | None:
    """从用户问题中提取商品最高预算。"""

    for pattern in BUDGET_PATTERNS:
        match = pattern.search(question)

        if match is None:
            continue

        max_price = Decimal(match.group(1))

        if max_price > 0:
            return max_price

    return None


def infer_knowledge_scope(
    question: str,
) -> tuple[
    Literal["product", "policy"] | None,
    str | None,
]:
    """单主题按标签检索，跨主题问题保留全部规则作为候选。"""

    matched_topics = []  # matched_topics：问题中命中的规则主题
    for topic, keywords in POLICY_TOPIC_KEYWORDS:
        # topic：主题标签；keywords：这个主题对应的关键词
        if any(
            keyword in question
            for keyword in keywords
        ):
            matched_topics.append(topic)

    if len(matched_topics) == 1:
        return "policy", matched_topics[0]

    if len(matched_topics) > 1:
        # None 表示不限定主题；仍然只检索规则，不混入商品资料。
        return "policy", None

    if any(
        keyword in question
        for keyword in PRODUCT_KEYWORDS
    ):
        return "product", None

    return None, None


def is_personal_refund_status_query(
    question: str,  # question：用户问题
) -> bool:
    """初步识别个人退款到账状态查询。"""

    normalized_question = "".join(question.split())
    # normalized_question：去除空白后的问题

    has_personal_reference = "我的" in normalized_question
    # has_personal_reference：是否明确提到个人记录

    has_refund = "退款" in normalized_question
    # has_refund：是否涉及退款

    asks_arrival_status = any(
        phrase in normalized_question
        for phrase in ("到账了吗", "到账了没", "有没有到账")
    )
    # phrase：一种表达
    # asks_arrival_status：是否询问实际到账状态

    return (
        has_personal_reference
        and has_refund
        and asks_arrival_status
    )
