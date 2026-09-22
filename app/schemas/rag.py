from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ProductKnowledgeMetadata(BaseModel):
    """商品知识中用于过滤、同步和引用的结构化信息。"""

    product_id: int = Field(ge=1)
    category_id: int = Field(ge=1)
    category_name: str = Field(min_length=1, max_length=30)
    price: Decimal = Field(gt=0)
    stock: int = Field(ge=0)


class ProductKnowledgeDocument(BaseModel):
    """一个等待生成 Embedding 的商品知识文档。"""

    source_type: Literal["product"] = "product"
    source_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)
    chunk_index: int = Field(default=0, ge=0)
    metadata: ProductKnowledgeMetadata

    @property
    def document_key(self) -> str:
        return (
            f"{self.source_type}:"
            f"{self.source_id}:"
            f"{self.chunk_index}"
        )


class PolicyKnowledgeMetadata(BaseModel):
    """规则知识的来源和引用信息。"""

    document_name: str = Field(
        min_length=1,
        max_length=100,
    )
    section: str = Field(
        min_length=1,
        max_length=100,
    )
    topic: str = Field(
        min_length=1,
        max_length=30,
    )
    source_file: str = Field(
        min_length=1,
        max_length=255,
    )


class PolicyKnowledgeDocument(BaseModel):
    """一个等待生成 Embedding 的商城规则分段。"""

    source_type: Literal["policy"] = "policy"
    source_id: str = Field(
        min_length=1,
        max_length=100,
    )
    title: str = Field(
        min_length=1,
        max_length=200,
    )
    content: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    metadata: PolicyKnowledgeMetadata

    @property
    def document_key(self) -> str:
        return (
            f"{self.source_type}:"
            f"{self.source_id}:"
            f"{self.chunk_index}"
        )


KnowledgeDocument = (
    ProductKnowledgeDocument
    | PolicyKnowledgeDocument
)


class RagQuestionRequest(BaseModel):
    """智能购物助手的问题请求。"""

    question: str = Field(
        min_length=1,
        max_length=500,
    )


class RagSourceResponse(BaseModel):
    """回答所引用的一条商城知识来源。"""

    citation_number: int = Field(ge=1)
    source_type: Literal["product", "policy"]
    source_id: str = Field(
        min_length=1,
        max_length=100,
    )
    title: str = Field(
        min_length=1,
        max_length=200,
    )


class RagAnswerResponse(BaseModel):
    """智能购物助手的回答。"""

    answer: str = Field(min_length=1)
    sources: list[RagSourceResponse] = Field(
        default_factory=list,
    )


PolicyTopic = Literal[
    "refund",
    "payment",
    "shipping",
]
# PolicyTopic：当前允许管理的规则主题类型


class RagPolicyRebuildResponse(BaseModel):
    """管理员重建一份规则知识后的响应。"""

    source_id: str = Field(
        min_length=1,
        max_length=100,
    )
    # source_id：完成重建的规则来源标识

    topic: PolicyTopic
    # topic：本次重建的规则主题

    synced_chunk_count: int = Field(ge=0)
    # synced_chunk_count：成功同步的知识分段数量


class RagProductSyncResponse(BaseModel):
    """管理员分批同步商品知识后的响应。"""

    synced_product_count: int = Field(ge=0)
    # synced_product_count：本批成功同步的商品数量

    next_after_id: int | None = Field(
        default=None,
        ge=1,
    )
    # next_after_id：下一批查询使用的商品ID游标