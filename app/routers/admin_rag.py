from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.rag.database import get_rag_db
from app.rag.providers.embedding import (
    LocalBgeEmbeddingProvider,
)
from app.rag.providers.factory import (
    get_embedding_provider,
)
from app.rag.services.policy_sync import (
    rebuild_policy_knowledge_by_topic,
)
from app.rag.services.product_sync import (
    sync_product_knowledge_batch,
)
from app.schemas.rag import (
    PolicyTopic,
    RagPolicyRebuildResponse,
    RagProductSyncResponse,
)



router = APIRouter(
    prefix="/admin/rag",
    tags=["管理员RAG"],
    dependencies=[Depends(get_current_admin)],
)
# dependencies：该Router下的接口都必须通过管理员验证

MysqlDatabase = Annotated[
    Session,
    Depends(get_db),
]
# MysqlDatabase：由FastAPI提供的MySQL数据库会话

RagDatabase = Annotated[
    Session,
    Depends(get_rag_db),
]
# RagDatabase：由FastAPI提供的RAG数据库会话


EmbeddingProvider = Annotated[
    LocalBgeEmbeddingProvider,
    Depends(get_embedding_provider),
]
# EmbeddingProvider：由FastAPI提供的BGE Provider


@router.post(
    "/policies/{topic}/rebuild",
    response_model=RagPolicyRebuildResponse,
)
def rebuild_policy_index(
    topic: Annotated[
        PolicyTopic,
        Path(description="需要重建的规则主题"),
    ],
    rag_db: RagDatabase,
    embedding_provider: EmbeddingProvider,
) -> RagPolicyRebuildResponse:
    """管理员重建指定主题的规则知识。"""

    source_id, synced_chunk_count = (
        rebuild_policy_knowledge_by_topic(
            rag_db=rag_db,
            embedding_provider=embedding_provider,
            topic=topic,
        )
    )
    # source_id：完成重建的规则来源标识
    # synced_chunk_count：成功同步的知识分段数量

    return RagPolicyRebuildResponse(
        source_id=source_id,
        topic=topic,
        synced_chunk_count=synced_chunk_count,
    )


@router.post(
    "/products/sync",
    response_model=RagProductSyncResponse,
)
def sync_product_index_batch(
    mysql_db: MysqlDatabase,
    rag_db: RagDatabase,
    embedding_provider: EmbeddingProvider,
    after_id: Annotated[
        int,
        Query(
            ge=0,
            description="从哪个商品ID之后开始同步",
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="本批最多同步多少件商品",
        ),
    ] = 100,
) -> RagProductSyncResponse:
    """管理员分批同步商品知识。"""

    synced_product_count, next_after_id = (
        sync_product_knowledge_batch(
            mysql_db=mysql_db,
            rag_db=rag_db,
            embedding_provider=embedding_provider,
            after_id=after_id,
            limit=limit,
        )
    )
    # synced_product_count：本批成功同步的商品数量
    # next_after_id：下一批查询使用的商品ID游标

    return RagProductSyncResponse(
        synced_product_count=synced_product_count,
        next_after_id=next_after_id,
    )
