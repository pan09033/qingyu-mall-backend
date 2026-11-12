"""客服数据访问；用户查询始终带 user_id，模型无法指定用户身份。"""

from datetime import datetime, timezone
from decimal import Decimal
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.support import SupportConversation, SupportTicket, SupportTurn


def get_conversation(db: Session, conversation_id: str, user_id: int) -> SupportConversation | None:
    return db.scalar(select(SupportConversation).where(
        SupportConversation.id == conversation_id, SupportConversation.user_id == user_id,
    ))


def list_conversations(db: Session, user_id: int, skip: int, limit: int) -> Sequence[SupportConversation]:
    return db.scalars(select(SupportConversation).where(
        SupportConversation.user_id == user_id,
    ).order_by(SupportConversation.updated_at.desc(), SupportConversation.id).offset(skip).limit(limit)).all()


def list_turns(db: Session, conversation_id: str) -> Sequence[SupportTurn]:
    return db.scalars(select(SupportTurn).where(
        SupportTurn.conversation_id == conversation_id,
    ).order_by(SupportTurn.id)).all()


def get_turn(db: Session, conversation_id: str, request_id: str) -> SupportTurn | None:
    return db.scalar(select(SupportTurn).where(
        SupportTurn.conversation_id == conversation_id, SupportTurn.request_id == request_id,
    ))


def advance_conversation(db: Session, conversation_id: str, version: int, **values) -> bool:
    # version：读取时的版本。只有版本未改变才能提交本轮结果。
    result = db.execute(update(SupportConversation).where(
        SupportConversation.id == conversation_id, SupportConversation.version == version,
    ).values(**values, version=version + 1, updated_at=datetime.now(timezone.utc).replace(tzinfo=None)),
        execution_options={"synchronize_session": False})
    return result.rowcount == 1


def get_conversation_ticket(db: Session, conversation_id: str) -> SupportTicket | None:
    return db.scalar(select(SupportTicket).where(SupportTicket.conversation_id == conversation_id))


def list_tickets(db: Session, ticket_status: str | None, skip: int, limit: int) -> tuple[Sequence[SupportTicket], int]:
    filters = [SupportTicket.status == ticket_status] if ticket_status else []
    items = db.scalars(select(SupportTicket).where(*filters).order_by(
        SupportTicket.updated_at.desc(), SupportTicket.id.desc(),
    ).offset(skip).limit(limit)).all()
    total = db.scalar(select(func.count()).select_from(SupportTicket).where(*filters))
    return items, total or 0


def get_ticket(db: Session, ticket_id: int) -> SupportTicket | None:
    return db.get(SupportTicket, ticket_id)


def update_ticket(db: Session, ticket_id: int, version: int, **values) -> bool:
    result = db.execute(update(SupportTicket).where(
        SupportTicket.id == ticket_id, SupportTicket.version == version,
    ).values(**values, version=version + 1, updated_at=datetime.now(timezone.utc).replace(tzinfo=None)),
        execution_options={"synchronize_session": False})
    return result.rowcount == 1


def find_budget_products(db: Session, max_price: Decimal, limit: int = 5) -> Sequence[Product]:
    # max_price：最高预算；纯价格筛选使用商城实时数据。
    return db.scalars(select(Product).where(Product.price <= max_price, Product.stock > 0)
        .order_by(Product.price, Product.id).limit(limit)).all()
