"""客服编排：授权、追问、只读工具、知识问答和人工工单。"""

import logging
import re
from collections.abc import Callable
from functools import wraps
from time import monotonic
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import AppError, ConflictError, ResourceNotFoundError
from app.models.support import SupportConversation, SupportTicket, SupportTurn
from app.rag.services.grounded_qa import answer_supported_question
from app.rag.services.query_analysis import extract_max_price, infer_knowledge_scope
from app.repositories import support as repository
from app.schemas.support import (
    AdminTicketDetail, AdminTicketResponse, ConversationDetail, ConversationResponse,
    SupportAnswer, SupportQuestion, TicketResponse, TicketUpdate, TurnResponse,
)
from app.services.support_tools import (
    extract_order_ids, is_budget_only_question, query_budget_products, query_owned_order,
)

logger = logging.getLogger(__name__)
MAX_TURNS = 100  # MAX_TURNS：每个会话最多保留的问答轮数


def database_operation(function: Callable) -> Callable:
    """数据库故障统一回滚，错误响应不暴露连接信息。"""
    @wraps(function)
    def wrapped(db: Session, *args, **kwargs):
        try:
            return function(db, *args, **kwargs)
        except SQLAlchemyError as error:
            db.rollback()
            logger.warning("support_database_failure type=%s", type(error).__name__)
            raise AppError(503, "客服记录服务暂时不可用，请稍后重试") from error
    return wrapped


def owned_conversation(db: Session, user_id: int, conversation_id: str) -> SupportConversation:
    conversation = repository.get_conversation(db, conversation_id, user_id)
    if conversation is None:
        raise ResourceNotFoundError("客服会话不存在")
    return conversation


@database_operation
def create_conversation(db: Session, user_id: int) -> ConversationResponse:
    conversation = SupportConversation(id=str(uuid4()), user_id=user_id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationResponse.model_validate(conversation)


@database_operation
def list_conversations(db: Session, user_id: int, skip: int, limit: int) -> list[ConversationResponse]:
    return [ConversationResponse.model_validate(item)
            for item in repository.list_conversations(db, user_id, skip, limit)]


@database_operation
def get_conversation(db: Session, user_id: int, conversation_id: str) -> ConversationDetail:
    conversation = owned_conversation(db, user_id, conversation_id)
    ticket = repository.get_conversation_ticket(db, conversation_id)
    return ConversationDetail(**ConversationResponse.model_validate(conversation).model_dump(),
        turns=[TurnResponse.model_validate(turn) for turn in repository.list_turns(db, conversation_id)],
        ticket=TicketResponse.model_validate(ticket) if ticket else None)


def decide_answer(
    db: Session, rag_db: Session, user_id: int, question: str, context: dict,
    embedding_factory: Callable, chat_factory: Callable,
) -> tuple[SupportAnswer, dict]:
    """返回本轮回答及新的上下文；业务读取工具不调用大模型。"""
    if (any(phrase in question for phrase in ("转人工", "人工客服", "人工处理", "找人工"))
            and not any(phrase in question for phrase in ("不要", "不用", "不想", "不需要"))):
        return SupportAnswer(answer="已提交人工客服工单，可以在当前会话查看处理状态和回复。", kind="handoff"), context

    order_ids = extract_order_ids(question)  # order_ids：用户明确提到的订单编号
    if len(order_ids) > 1:
        return SupportAnswer(answer="请一次提供一个订单编号，我会逐笔查询。", kind="clarification"), {}
    pending = context.get("pending_order_question")  # pending：上一轮缺少订单号的问题
    if pending and re.fullmatch(r"[1-9]\d{0,9}", question):
        order_ids = {int(question)}
    personal = any(word in question for word in ("我的订单", "我的退款", "我的退货", "查订单", "查询订单", "查一下订单", "查下订单"))
    followup = bool(re.match(r"^(那|这单|这一单|这个订单|这笔|它|能退|可以退|怎么退|如何退|还能|还可以)", question))
    general_policy = any(word in question for word in ("商城", "一般", "通常", "规则", "支付方式"))
    order_context = context.get("mode") == "order" and followup and not general_policy
    if order_ids or personal or order_context:
        order_id = next(iter(order_ids), None)
        if order_id is None and order_context:
            order_id = context.get("order_id")
        if order_id is None:
            return SupportAnswer(answer="请提供要查询的订单编号，例如“订单123发货了吗？”；我只能查询你本人名下的订单。",
                                 kind="clarification"), {"pending_order_question": question}
        effective_question = f"{pending}\n{question}" if pending else question
        answer = query_owned_order(db, user_id, order_id, effective_question)
        new_context = {"mode": "order", "order_id": order_id} if answer.order else {}
        return answer, new_context

    scope, _topic = infer_knowledge_scope(question)
    max_price = extract_max_price(question) if scope != "policy" else None
    if max_price is not None and is_budget_only_question(question):
        return query_budget_products(db, max_price), {"mode": "products"}

    effective_question = question
    if followup and context.get("mode") == "knowledge":
        previous_question = context.get("knowledge_question", "")  # previous_question：上一轮独立问题
        effective_question = f"之前的问题：{previous_question}\n用户追问：{question}"
    elif followup and not context:
        return SupportAnswer(answer="请补充你指的是哪笔订单或哪项商城规则，我目前还没有足够的上下文。",
                             kind="clarification"), {}
    answer = answer_supported_question(rag_db, effective_question, embedding_factory, chat_factory,
                                      settings.rag_minimum_similarity, settings.rag_retrieval_limit)
    new_context = {"mode": "knowledge", "knowledge_question":
        context.get("knowledge_question", question) if followup else question}
    return answer, new_context


@database_operation
def send_message(db: Session, rag_db: Session, user_id: int, conversation_id: str,
                 data: SupportQuestion, embedding_factory: Callable, chat_factory: Callable) -> TurnResponse:
    started = monotonic()
    conversation = owned_conversation(db, user_id, conversation_id)
    request_id = str(data.request_id)
    existing = repository.get_turn(db, conversation_id, request_id)
    if existing:
        if existing.question != data.question:
            raise ConflictError("同一个请求编号不能用于不同问题")
        return TurnResponse.model_validate(existing)
    if len(repository.list_turns(db, conversation_id)) >= MAX_TURNS:
        raise ConflictError("本次会话已达到100轮，请新建会话继续")
    version, context, title = conversation.version, dict(conversation.context), conversation.title
    db.rollback()  # 调用模型前结束读事务，不持有会话行锁。
    answer, new_context = decide_answer(db, rag_db, user_id, data.question, context, embedding_factory, chat_factory)
    if not repository.advance_conversation(db, conversation_id, version, context=new_context,
                                          title=data.question[:100] if title == "新的客服会话" else title):
        db.rollback()
        existing = repository.get_turn(db, conversation_id, request_id)
        if existing and existing.question == data.question:
            return TurnResponse.model_validate(existing)
        raise ConflictError("会话有新消息，请刷新后重试")
    if answer.kind == "handoff":
        ticket = repository.get_conversation_ticket(db, conversation_id)
        if ticket is None:
            ticket = SupportTicket(conversation_id=conversation_id, user_id=user_id, reason=data.question)
            db.add(ticket)
            db.flush()
        answer.answer = f"人工工单 #{ticket.id} 已保存。请在当前会话查看处理状态和人工回复。"
        if ticket.status == "resolved":
            answer.answer = f"本会话的工单 #{ticket.id} 已解决，可在上方查看回复。如有新的问题，请新建会话并提交工单。"
    turn = SupportTurn(conversation_id=conversation_id, request_id=request_id,
                       question=data.question, response=answer.model_dump(mode="json"))
    db.add(turn)
    db.commit()
    db.refresh(turn)
    logger.info("support_answer conversation=%s route=%s sources=%d elapsed_ms=%d",
                conversation_id, answer.kind, len(answer.sources), (monotonic() - started) * 1000)
    return TurnResponse.model_validate(turn)


@database_operation
def handoff(db: Session, user_id: int, conversation_id: str, reason: str) -> TicketResponse:
    conversation = owned_conversation(db, user_id, conversation_id)
    ticket = repository.get_conversation_ticket(db, conversation_id)
    if ticket:
        return TicketResponse.model_validate(ticket)
    if not repository.advance_conversation(db, conversation_id, conversation.version):
        db.rollback()
        ticket = repository.get_conversation_ticket(db, conversation_id)
        if ticket:
            return TicketResponse.model_validate(ticket)
        raise ConflictError("会话已更新，请刷新后重试")
    ticket = SupportTicket(conversation_id=conversation_id, user_id=user_id, reason=reason)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return TicketResponse.model_validate(ticket)


@database_operation
def list_admin_tickets(db: Session, ticket_status: str | None, skip: int, limit: int) -> dict:
    items, total = repository.list_tickets(db, ticket_status, skip, limit)
    return {"items": [AdminTicketResponse.model_validate(item) for item in items], "total": total}


@database_operation
def get_admin_ticket(db: Session, ticket_id: int) -> AdminTicketDetail:
    ticket = repository.get_ticket(db, ticket_id)
    if ticket is None:
        raise ResourceNotFoundError("工单不存在")
    return AdminTicketDetail(**AdminTicketResponse.model_validate(ticket).model_dump(),
        turns=[TurnResponse.model_validate(turn) for turn in repository.list_turns(db, ticket.conversation_id)])


@database_operation
def update_admin_ticket(db: Session, admin_id: int, ticket_id: int, data: TicketUpdate) -> AdminTicketDetail:
    if repository.get_ticket(db, ticket_id) is None:
        raise ResourceNotFoundError("工单不存在")
    if not repository.update_ticket(db, ticket_id, data.version, status=data.status,
                                    reply=data.reply, assigned_admin_id=admin_id):
        db.rollback()
        raise ConflictError("工单已被其他管理员更新，请刷新后重试")
    db.commit()
    return get_admin_ticket(db, ticket_id)
