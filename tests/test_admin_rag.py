from collections.abc import Generator
from unittest.mock import ANY, Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.rag.database import get_rag_db
from app.rag.providers.embedding import (
    LocalBgeEmbeddingProvider,
)
from app.rag.providers.factory import get_embedding_provider


@pytest.fixture
def admin_rag_dependencies() -> Generator[
    tuple[Session, LocalBgeEmbeddingProvider],
    None,
    None,
]:
    """用Mock替换管理员重建接口的外部依赖。"""

    rag_db = Mock(spec=Session)
    # rag_db：模拟RAG数据库会话
    embedding_provider = Mock(
        spec=LocalBgeEmbeddingProvider,
    )
    # embedding_provider：模拟BGE Provider

    def override_rag_db() -> Generator[Session, None, None]:
        yield rag_db

    def override_embedding_provider() -> LocalBgeEmbeddingProvider:
        return embedding_provider

    app.dependency_overrides[get_rag_db] = override_rag_db
    app.dependency_overrides[get_embedding_provider] = (
        override_embedding_provider
    )

    yield rag_db, embedding_provider

    app.dependency_overrides.pop(get_rag_db, None)
    app.dependency_overrides.pop(get_embedding_provider, None)


def test_policy_rebuild_requires_login(
    client: TestClient,
    admin_rag_dependencies: tuple[
        Session,
        LocalBgeEmbeddingProvider,
    ],
) -> None:
    with patch(
        "app.routers.admin_rag."
        "rebuild_policy_knowledge_by_topic",
    ) as rebuild:
        response = client.post(
            "/admin/rag/policies/shipping/rebuild",
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    rebuild.assert_not_called()


def test_regular_user_cannot_rebuild_policy_knowledge(
    client: TestClient,
    auth_headers: dict[str, str],
    admin_rag_dependencies: tuple[
        Session,
        LocalBgeEmbeddingProvider,
    ],
) -> None:
    with patch(
        "app.routers.admin_rag."
        "rebuild_policy_knowledge_by_topic",
    ) as rebuild:
        response = client.post(
            "/admin/rag/policies/shipping/rebuild",
            headers=auth_headers,
        )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    rebuild.assert_not_called()


def test_admin_can_rebuild_policy_knowledge(
    client: TestClient,
    admin_headers: dict[str, str],
    admin_rag_dependencies: tuple[
        Session,
        LocalBgeEmbeddingProvider,
    ],
) -> None:
    rag_db, embedding_provider = admin_rag_dependencies

    with patch(
        "app.routers.admin_rag."
        "rebuild_policy_knowledge_by_topic",
        return_value=("shipping_policy", 5),
    ) as rebuild:
        response = client.post(
            "/admin/rag/policies/shipping/rebuild",
            headers=admin_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "source_id": "shipping_policy",
        "topic": "shipping",
        "synced_chunk_count": 5,
    }
    rebuild.assert_called_once_with(
        rag_db=rag_db,
        embedding_provider=embedding_provider,
        topic="shipping",
    )


def test_policy_rebuild_rejects_unknown_topic(
    client: TestClient,
    admin_headers: dict[str, str],
    admin_rag_dependencies: tuple[
        Session,
        LocalBgeEmbeddingProvider,
    ],
) -> None:
    with patch(
        "app.routers.admin_rag."
        "rebuild_policy_knowledge_by_topic",
    ) as rebuild:
        response = client.post(
            "/admin/rag/policies/holiday/rebuild",
            headers=admin_headers,
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    rebuild.assert_not_called()


def test_admin_can_sync_product_knowledge_batch(
    client: TestClient,
    admin_headers: dict[str, str],
    admin_rag_dependencies: tuple[
        Session,
        LocalBgeEmbeddingProvider,
    ],
) -> None:
    """管理员可以指定游标和数量分批同步商品知识。"""

    rag_db, embedding_provider = admin_rag_dependencies

    with patch(
        "app.routers.admin_rag."
        "sync_product_knowledge_batch",
        return_value=(2, 12),
    ) as sync_products:
        response = client.post(
            "/admin/rag/products/sync",
            params={
                "after_id": 10,
                "limit": 2,
            },
            headers=admin_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "synced_product_count": 2,
        "next_after_id": 12,
    }
    sync_products.assert_called_once_with(
        mysql_db=ANY,
        rag_db=rag_db,
        embedding_provider=embedding_provider,
        after_id=10,
        limit=2,
    )


@pytest.mark.parametrize(
    "query_parameters",
    [
        {"after_id": -1},
        {"limit": 0},
        {"limit": 101},
    ],
)
def test_product_sync_rejects_invalid_query_parameters(
    client: TestClient,
    admin_headers: dict[str, str],
    admin_rag_dependencies: tuple[
        Session,
        LocalBgeEmbeddingProvider,
    ],
    query_parameters: dict[str, int],
) -> None:
    """非法游标或批次大小应在进入Service前被拒绝。"""

    with patch(
        "app.routers.admin_rag."
        "sync_product_knowledge_batch",
    ) as sync_products:
        response = client.post(
            "/admin/rag/products/sync",
            params=query_parameters,
            headers=admin_headers,
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    sync_products.assert_not_called()
