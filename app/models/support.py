"""客服会话、问答记录和人工工单，保存在商城 MySQL 中。"""

from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    """MySQL的DateTime无时区，统一以UTC写入，接口返回时补充时区。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SupportConversation(Base):
    __tablename__ = "support_conversations"
    __table_args__ = (Index("ix_support_conversations_user_updated", "user_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # id：会话编号
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), default="新的客服会话")
    context: Mapped[dict] = mapped_column(JSON, default=dict)  # context：服务端维护的追问上下文
    version: Mapped[int] = mapped_column(default=0)  # version：防止并发请求覆盖上下文
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, server_default=func.now())


class SupportTurn(Base):
    __tablename__ = "support_turns"
    __table_args__ = (
        UniqueConstraint("conversation_id", "request_id", name="uq_support_turn_request"),
        Index("ix_support_turns_conversation_id", "conversation_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("support_conversations.id"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36))  # request_id：重试时保持不变，避免重复保存
    question: Mapped[str] = mapped_column(String(500))
    response: Mapped[dict] = mapped_column(JSON)  # response：回答、引用和安全的订单摘要
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, server_default=func.now())


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'in_progress', 'resolved')", name="ck_support_tickets_status"),
        Index("ix_support_tickets_status_updated", "status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("support_conversations.id"), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="open")
    reply: Mapped[str] = mapped_column(Text, default="")  # reply：用户可见的人工回复
    assigned_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, server_default=func.now())
