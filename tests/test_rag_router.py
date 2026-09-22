from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.rag.database import get_rag_db
from app.rag.exceptions import RagServiceUnavailableError
from app.rag.providers.factory import (
    get_chat_provider,
    get_embedding_provider,
)
from app.schemas.rag import (
    RagAnswerResponse,
    RagSourceResponse,
)


@pytest.fixture
def rag_dependencies(
    client: TestClient,
) -> Generator[Session, None, None]:
    rag_db = Mock(spec=Session)

    def override_rag_db() -> Generator[Session, None, None]:
        yield rag_db

    app.dependency_overrides[get_rag_db] = override_rag_db

    yield rag_db

    app.dependency_overrides.pop(get_rag_db, None)


def test_question_endpoint_requires_login(
    client: TestClient,
    rag_dependencies: Session,
) -> None:
    with patch(
        "app.routers.rag.answer_question",
    ) as answer:
        response = client.post(
            "/assistant/questions",
            json={
                "question": "预算500元以内有什么耳机？",
            },
        )

    assert response.status_code == 401
    answer.assert_not_called()


def test_question_endpoint_returns_answer_and_sources(
    client: TestClient,
    auth_headers: dict[str, str],
    rag_dependencies: Session,
) -> None:
    rag_db = rag_dependencies
    service_response = RagAnswerResponse(
        answer="已发货订单需要申请退货退款。[资料1]",
        sources=[
            RagSourceResponse(
                citation_number=1,
                source_type="policy",
                source_id="refund_policy",
                title="商城退款规则 - 已发货订单",
            ),
        ],
    )

    with patch(
        "app.routers.rag.answer_question",
        return_value=service_response,
    ) as answer:
        response = client.post(
            "/assistant/questions",
            headers=auth_headers,
            json={
                "question": "已经发货怎样退款？",
            },
        )

    assert response.status_code == 200
    assert response.json() == service_response.model_dump()
    answer.assert_called_once_with(
        rag_db=rag_db,
        embedding_provider_factory=get_embedding_provider,
        chat_provider_factory=get_chat_provider,
        question="已经发货怎样退款？",
        minimum_similarity=0.50,
        limit=5,
    )


def test_personal_refund_question_returns_guidance_without_ai(
    client: TestClient,  # client：测试用HTTP客户端
    auth_headers: dict[str, str],  # auth_headers：测试用户的登录请求头
    rag_dependencies: Session,
) -> None:
    rag_db = rag_dependencies
    # rag_db：模拟RAG数据库会话

    with (
        patch(
            "app.routers.rag.get_embedding_provider",
        ) as embedding_provider_factory,
        patch(
            "app.routers.rag.get_chat_provider",
        ) as chat_provider_factory,
        patch(
            "app.rag.services.qa.retrieve_knowledge",
        ) as retrieve,
    ):
        # 两个factory：监视Router传入的获取函数是否被调用
        # retrieve：模拟检索函数，用于确认它没有被调用
        response = client.post(
            "/assistant/questions",
            headers=auth_headers,
            json={"question": "我的退款到账了吗？"},
        )
        # response：接口响应，经过真实Router和Service

    assert response.status_code == 200
    assert response.json() == {
        "answer": (
            "我目前无法查询你的个人退款到账情况。"
            "请查看支付账户的实际入账记录。"
        ),
        "sources": [],
    }
    retrieve.assert_not_called()
    assert rag_db.mock_calls == []
    embedding_provider_factory.assert_not_called()
    chat_provider_factory.assert_not_called()


def test_question_endpoint_returns_503_when_chat_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    rag_dependencies: Session,
) -> None:
    with patch(
        "app.routers.rag.answer_question",
        side_effect=RagServiceUnavailableError(),
    ):
        response = client.post(
            "/assistant/questions",
            headers=auth_headers,
            json={
                "question": "已经发货怎样退款？",
            },
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "智能购物助手暂时不可用，请稍后重试",
    }
