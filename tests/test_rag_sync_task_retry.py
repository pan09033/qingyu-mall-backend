from datetime import datetime, timedelta

import pytest

from app.models.rag_product_sync_task import RagProductSyncTask
from app.rag.services.product_sync_tasks import schedule_product_sync_task_retry


@pytest.mark.parametrize("previous_count", [0, 1, 2])
def test_retry_delay_and_failure_limit(previous_count: int) -> None:
    now = datetime(2026, 9, 21, 10)
    task = RagProductSyncTask(
        product_id=123, retry_count=previous_count,
        status="processing", available_at=now,
    )
    schedule_product_sync_task_retry(
        task, RuntimeError("private diagnostic text"), now,
    )
    assert task.retry_count == previous_count + 1
    assert task.completed_at is None
    assert task.last_error == "RuntimeError"
    if previous_count < 2:
        assert task.status == "pending"
        assert task.available_at == now + timedelta(seconds=10)
    else:
        assert task.status == "failed"
        assert task.available_at == now
