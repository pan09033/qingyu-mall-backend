from app.models.product import Product
from app.schemas.rag import (
    ProductKnowledgeDocument,
    ProductKnowledgeMetadata,
)


def build_product_knowledge_document(
    product: Product,
) -> ProductKnowledgeDocument:
    """把一条 MySQL 商品记录转换成知识文档。"""

    category_name = product.category.name
    description = product.description or "暂无商品描述"

    content = (
        f"商品名称：{product.name}。"
        f"商品分类：{category_name}。"
        f"商品描述：{description}"
    )

    metadata = ProductKnowledgeMetadata(
        product_id=product.id,
        category_id=product.category_id,
        category_name=category_name,
        price=product.price,
        stock=product.stock,
    )

    return ProductKnowledgeDocument(
        source_id=str(product.id),
        title=product.name,
        content=content,
        metadata=metadata,
    )