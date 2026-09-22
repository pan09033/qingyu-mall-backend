from decimal import Decimal

from app.models.category import Category
from app.models.product import Product
from app.rag.ingestion.product import (
    build_product_knowledge_document,
)


def build_product(description: str | None) -> Product:
    category = Category(
        id=3,
        name="耳机",
    )
    return Product(
        id=15,
        name="静音降噪蓝牙耳机",
        price=Decimal("399.00"),
        stock=8,
        description=description,
        category_id=category.id,
        category=category,
    )


def test_build_product_knowledge_document() -> None:
    product = build_product(
        "适合办公室和通勤使用。"
    )

    document = build_product_knowledge_document(product)

    assert document.document_key == "product:15:0"
    assert document.title == "静音降噪蓝牙耳机"
    assert document.content == (
        "商品名称：静音降噪蓝牙耳机。"
        "商品分类：耳机。"
        "商品描述：适合办公室和通勤使用。"
    )
    assert document.metadata.product_id == 15
    assert document.metadata.price == Decimal("399.00")
    assert document.metadata.stock == 8


def test_build_product_knowledge_document_handles_missing_description(
) -> None:
    product = build_product(None)

    document = build_product_knowledge_document(product)

    assert document.content.endswith(
        "商品描述：暂无商品描述"
    )
