"""客服接口的数据校验；身份和历史上下文不接受客户端指定。"""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.rag import RagSourceResponse

TicketStatus = Literal["open", "in_progress", "resolved"]  # TicketStatus：工单状态


class TimestampResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", "updated_at", check_fields=False)
    @classmethod
    def attach_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class SupportQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=500)
    request_id: UUID  # request_id：一次提问的唯一请求编号


class HandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(default="用户请求人工客服处理", min_length=1, max_length=500)


class SupportSource(RagSourceResponse):
    excerpt: str = ""  # excerpt：模型引用且通过原文校验的片段


class OrderSummary(BaseModel):
    order_id: int
    status: str
    status_label: str
    total_amount: str
    refund_status: str | None = None
    refund_status_label: str | None = None


class SupportAnswer(BaseModel):
    answer: str
    kind: Literal["knowledge", "no_knowledge", "order", "clarification", "handoff", "products"]
    sources: list[SupportSource] = Field(default_factory=list)
    order: OrderSummary | None = None
    handoff_available: bool = False


class TurnResponse(TimestampResponse):
    model_config = ConfigDict(from_attributes=True)
    id: int
    request_id: str
    question: str
    response: SupportAnswer
    created_at: datetime


class TicketResponse(TimestampResponse):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_id: str
    reason: str
    status: TicketStatus
    reply: str
    version: int
    created_at: datetime
    updated_at: datetime


class ConversationResponse(TimestampResponse):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationResponse):
    turns: list[TurnResponse]
    ticket: TicketResponse | None = None


class TicketUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: TicketStatus
    reply: str = Field(default="", max_length=2000, validate_default=True)
    version: int = Field(ge=0)

    @field_validator("reply")
    @classmethod
    def require_resolution_reply(cls, value, info):
        if info.data.get("status") == "resolved" and not value:
            raise ValueError("解决工单时需要填写给用户的回复")
        return value


class AdminTicketResponse(TicketResponse):
    user_id: int
    assigned_admin_id: int | None


class AdminTicketDetail(AdminTicketResponse):
    turns: list[TurnResponse]


class TicketList(BaseModel):
    items: list[AdminTicketResponse]
    total: int
