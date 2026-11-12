from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.schemas.support import AdminTicketDetail, TicketList, TicketStatus, TicketUpdate
from app.services import support

router = APIRouter(prefix="/admin/support/tickets", tags=["管理员客服工单"], dependencies=[Depends(get_current_admin)])
Database = Annotated[Session, Depends(get_db)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
TicketId = Annotated[int, Path(ge=1)]


@router.get("", response_model=TicketList)
def list_tickets(db: Database, status: TicketStatus | None = None,
                 skip: Annotated[int, Query(ge=0)] = 0,
                 limit: Annotated[int, Query(ge=1, le=50)] = 20):
    return support.list_admin_tickets(db, status, skip, limit)


@router.get("/{ticket_id}", response_model=AdminTicketDetail)
def get_ticket(ticket_id: TicketId, db: Database):
    return support.get_admin_ticket(db, ticket_id)


@router.patch("/{ticket_id}", response_model=AdminTicketDetail)
def update_ticket(ticket_id: TicketId, data: TicketUpdate, db: Database, admin: CurrentAdmin):
    return support.update_admin_ticket(db, admin.id, ticket_id, data)
