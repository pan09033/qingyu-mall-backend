from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models.rag_product_sync_task import RagProductSyncTask
from app.rag.services.product_sync_tasks import create_product_sync_task
from app.rag.sync_task_types import ProductSyncOperation, RagSyncTaskStatus


@pytest.mark.parametrize("operation", list(ProductSyncOperation))
def test_create_task_leaves_commit_to_caller(operation):
    db = Mock(spec=Session)
    task = create_product_sync_task(db, 123, operation)

    assert task.product_id == 123
    assert task.operation == operation.value
    assert task.status == RagSyncTaskStatus.PENDING.value
    db.add.assert_called_once_with(task)
    db.commit.assert_not_called()


@pytest.mark.parametrize("product_id", [0, -1])
def test_invalid_product_id_does_not_add_task(product_id):
    db = Mock(spec=Session)
    with pytest.raises(ValueError, match="商品ID必须大于0"):
        create_product_sync_task(db, product_id, ProductSyncOperation.UPSERT)
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_caller_controls_task_commit_and_rollback():
    # engine：独立的临时数据库，不连接真实MySQL
    engine = create_engine("sqlite://")
    try:
        RagProductSyncTask.__table__.create(engine)
        with Session(engine) as db:
            create_product_sync_task(db, 123, ProductSyncOperation.UPSERT)
            db.flush()
            db.rollback()

        with Session(engine) as db:
            assert db.scalar(
                select(func.count()).select_from(RagProductSyncTask)
            ) == 0
            create_product_sync_task(db, 456, ProductSyncOperation.DELETE)
            db.commit()

        with Session(engine) as db:
            task = db.scalar(select(RagProductSyncTask))
            assert task is not None
            assert task.product_id == 456
            assert task.operation == "delete"
    finally:
        engine.dispose()
