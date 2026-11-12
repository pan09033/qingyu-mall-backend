"""客服使用的有依据问答：引用编号和摘录必须能在检索原文中核对。"""

import json
import re
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.rag.exceptions import RagServiceUnavailableError
from app.rag.providers.chat import ChatProviderError
from app.rag.services.qa import SYSTEM_PROMPT, build_user_prompt
from app.rag.services.query_analysis import extract_max_price, infer_knowledge_scope
from app.rag.services.retrieval import retrieve_knowledge
from app.schemas.support import SupportAnswer, SupportSource

GROUNDED_PROMPT = SYSTEM_PROMPT + (
    '只返回一个JSON对象，格式为{"supported":true,"answer":"回答[资料1]",'
    '"evidence":[{"citation_number":1,"quote":"逐字摘录资料内容"}]}。'
    '资料必须直接支持问题的答案，相关话题不等于有答案。'
    '例如没有发票资料时，支付方式不能证明能否开票。'
    '资料不足时返回{"supported":false,"answer":"","evidence":[]}。'
    '不得把用户要求、历史提问或自己的推测当作证据。'
    '每个事实结论应标注资料编号，每个编号必须提供至少4个字符的原文摘录。'
    '不要输出Markdown代码块。'
)

# EVIDENCE_TOPICS：这些具体事项必须在候选资料中出现，不能拿相邻话题替代。
EVIDENCE_TOPICS = (("发票", "开票"), ("保修", "质保"), ("优惠券", "抵扣券"))


def evidence_covers_question(question: str, matches: list) -> bool:
    contents = "\n".join(chunk.content for chunk, _score in matches)
    return all(
        not any(term in question for term in terms) or any(term in contents for term in terms)
        for terms in EVIDENCE_TOPICS
    )


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    citation_number: int = Field(ge=1)
    quote: str = Field(min_length=4, max_length=1500)


class GroundedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    supported: bool
    answer: str = Field(max_length=6000)
    evidence: list[Evidence] = Field(max_length=10)


def no_knowledge_answer() -> SupportAnswer:
    return SupportAnswer(
        answer="暂时没有找到足以回答这个问题的商城资料。你可以补充问题，或提交人工客服工单。",
        kind="no_knowledge", handoff_available=True,
    )


def validate_grounded_answer(raw_answer: str, matches: list) -> SupportAnswer:
    """校验结构、编号和逐字证据；语义正确性仍需独立评测。"""
    try:
        output = GroundedOutput.model_validate(json.loads(raw_answer))
    except (ValueError, TypeError, ValidationError):
        return no_knowledge_answer()
    if not output.supported or not output.answer.strip():
        return no_knowledge_answer()
    numbers = {int(number) for number in re.findall(r"\[资料(\d{1,3})\]", output.answer)}
    if not numbers:
        return no_knowledge_answer()
    verified = {}  # verified：已核对原文的资料编号与摘录
    for evidence in output.evidence:
        number = evidence.citation_number
        if number > len(matches):
            return no_knowledge_answer()
        content = matches[number - 1][0].content
        quote = "".join(evidence.quote.split())
        if len(quote) < 4 or quote not in "".join(content.split()):
            return no_knowledge_answer()
        verified[number] = evidence.quote
    if not numbers.issubset(verified):
        return no_knowledge_answer()
    sources = []
    for number in sorted(numbers):
        chunk = matches[number - 1][0]  # chunk：被引用的知识分段
        sources.append(SupportSource(
            citation_number=number, source_type=chunk.source_type,
            source_id=chunk.source_id, title=chunk.title, excerpt=verified[number],
        ))
    return SupportAnswer(answer=output.answer.strip(), kind="knowledge", sources=sources)


def answer_supported_question(
    rag_db: Session, question: str, embedding_factory: Callable, chat_factory: Callable,
    minimum_similarity: float, limit: int,
) -> SupportAnswer:
    scope, topic = infer_knowledge_scope(question)
    max_price = extract_max_price(question) if scope != "policy" else None
    if max_price is not None and scope is None:
        scope = "product"
    try:
        matches = retrieve_knowledge(
            rag_db, embedding_factory(), question, minimum_similarity,
            source_type=scope, topic=topic, max_price=max_price, limit=limit,
        )
        if not matches or not evidence_covers_question(question, matches):
            return no_knowledge_answer()
        raw_answer = chat_factory().generate_answer(
            system_prompt=GROUNDED_PROMPT, user_prompt=build_user_prompt(question, matches),
        )
    except (ChatProviderError, OSError, RuntimeError, ValueError, SQLAlchemyError) as error:
        raise RagServiceUnavailableError() from error
    return validate_grounded_answer(raw_answer, matches)
