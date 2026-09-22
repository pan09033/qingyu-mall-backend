from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user
from app.models.user import User
from app.rag.database import get_rag_db
from app.rag.providers.factory import (
    get_chat_provider,
    get_embedding_provider,
)
from app.rag.services.qa import answer_question
from app.schemas.rag import (
    RagAnswerResponse,
    RagQuestionRequest,
)


router = APIRouter(
    prefix="/assistant",
    tags=["智能购物助手"],
)

RagDatabase = Annotated[
    Session,
    Depends(get_rag_db),
]
CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]


@router.post(
    "/questions",
    response_model=RagAnswerResponse,
)
def ask_question(
    question_data: RagQuestionRequest,
    _current_user: CurrentUser,
    rag_db: RagDatabase,
) -> RagAnswerResponse:
    """根据商城知识回答当前用户的问题。"""

    return answer_question(
        rag_db=rag_db,
        embedding_provider_factory=get_embedding_provider,
        # embedding_provider_factory：按需获取BGE的函数
        chat_provider_factory=get_chat_provider,
        # chat_provider_factory：按需获取DeepSeek Provider的函数
        question=question_data.question,
        minimum_similarity=(
            settings.rag_minimum_similarity
        ),
        limit=settings.rag_retrieval_limit,
    )
