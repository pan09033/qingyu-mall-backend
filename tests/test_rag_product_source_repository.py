from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product
from app.rag.repositories.product_source import (
    get_product_batch_for_knowledge_sync,
    get_product_for_knowledge_sync,
)


def test_product_sync_query_uses_keyset_pagination() -> None:
    mysql_db = Mock(spec=Session)
    expected_products = [object(), object()]
    scalar_result = Mock()
    scalar_result.all.return_value = expected_products
    mysql_db.scalars.return_value = scalar_result

    products = get_product_batch_for_knowledge_sync(
        mysql_db,
        after_id=7,
        limit=3,
    )

    statement = mysql_db.scalars.call_args.args[0]
    compiled_sql = str(
        statement.compile(
            dialect=mysql.dialect(),
            compile_kwargs={
                "literal_binds": True,
            },
        )
    )

    assert "products.id > 7" in compiled_sql
    assert "ORDER BY products.id ASC" in compiled_sql
    assert "LIMIT 3" in compiled_sql
    assert len(statement._with_options) == 1
    assert products is expected_products


def test_single_product_query_loads_category_and_handles_missing() -> None:
    engine = create_engine("sqlite://")
    try:
        Category.__table__.create(engine)
        Product.__table__.create(engine)
        with Session(engine) as db:
            category = Category(name="耳机", description="测试分类")
            product = Product(
                name="测试耳机", price=399, stock=5,
                description="办公使用", category=category,
            )
            other = Product(name="其他商品", price=99, stock=1, category=category)
            db.add_all([product, other])
            db.commit()
            product_id = product.id

        with Session(engine) as db:
            found = get_product_for_knowledge_sync(db, product_id)
            assert found is not None
            assert found.id == product_id
            assert get_product_for_knowledge_sync(db, 999999) is None

        # 关闭会话后仍可读取分类，证明查询时已加载。
        assert found.category.name == "耳机"
    finally:
        engine.dispose()
