from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.rag_product_sync_task import RagProductSyncTask
from app.rag.services.product_sync_tasks import execute_product_sync_task


@pytest.mark.parametrize("operation, exists", [
    ("delete", True), ("upsert", False), ("upsert", True), ("unknown", True),
])
def test_task_dispatch_and_lazy_embedding(operation: str, exists: bool) -> None:
    mysql_db = Mock(spec=Session)
    rag_db = Mock(spec=Session)
    task = RagProductSyncTask(id=5, product_id=123, operation=operation, status="pending")
    product = object() if exists else None
    prefix = "app.rag.services.product_sync_tasks."
    with (
        patch(prefix + "get_product_for_knowledge_sync", return_value=product) as get_product,
        patch(prefix + "get_embedding_provider") as get_provider,
        patch(prefix + "delete_product_knowledge") as delete,
        patch(prefix + "sync_product_knowledge") as sync,
    ):
        if operation == "unknown":
            with pytest.raises(ValueError, match="不支持"):
                execute_product_sync_task(mysql_db, rag_db, task)
            get_product.assert_not_called()
            delete.assert_not_called()
        else:
            execute_product_sync_task(mysql_db, rag_db, task)
            if operation == "delete":
                get_product.assert_not_called()
            else:
                get_product.assert_called_once_with(mysql_db=mysql_db, product_id=123)
            if operation == "delete" or not exists:
                delete.assert_called_once_with(rag_db=rag_db, product_id=123)
            else:
                delete.assert_not_called()
        if operation == "upsert" and exists:
            get_provider.assert_called_once_with()
            sync.assert_called_once_with(
                rag_db=rag_db, product=product, embedding_provider=get_provider.return_value,
            )
        else:
            get_provider.assert_not_called()
            sync.assert_not_called()
    assert task.status == "pending"
    mysql_db.commit.assert_not_called()


def test_execution_failure_propagates_without_completing_task() -> None:
    task = RagProductSyncTask(product_id=123, operation="delete", status="processing")
    with patch(
        "app.rag.services.product_sync_tasks.delete_product_knowledge",
        side_effect=RuntimeError("simulated failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated failure"):
            execute_product_sync_task(Mock(spec=Session), Mock(spec=Session), task)
    assert task.status == "processing"
