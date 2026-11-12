"""用户客服接口；会话与订单身份均来自登录凭证。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.rag.database import get_rag_db
from app.rag.providers.factory import get_chat_provider, get_embedding_provider
from app.schemas.support import ConversationDetail, ConversationResponse, HandoffRequest, SupportQuestion, TicketResponse, TurnResponse
from app.services import support

router = APIRouter(prefix="/support", tags=["商城智能客服"])
Database = Annotated[Session, Depends(get_db)]
RagDatabase = Annotated[Session, Depends(get_rag_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation(db: Database, user: CurrentUser):
    return support.create_conversation(db, user.id)


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(db: Database, user: CurrentUser,
                       skip: Annotated[int, Query(ge=0)] = 0,
                       limit: Annotated[int, Query(ge=1, le=50)] = 20):
    return support.list_conversations(db, user.id, skip, limit)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: UUID, db: Database, user: CurrentUser):
    return support.get_conversation(db, user.id, str(conversation_id))


@router.post("/conversations/{conversation_id}/messages", response_model=TurnResponse)
def send_message(conversation_id: UUID, data: SupportQuestion, db: Database, rag_db: RagDatabase, user: CurrentUser):
    return support.send_message(db, rag_db, user.id, str(conversation_id), data,
                                get_embedding_provider, get_chat_provider)


@router.post("/conversations/{conversation_id}/handoff", response_model=TicketResponse)
def handoff(conversation_id: UUID, data: HandoffRequest, db: Database, user: CurrentUser):
    return support.handoff(db, user.id, str(conversation_id), data.reason)
