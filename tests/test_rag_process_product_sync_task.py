from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.rag_product_sync_task import RagProductSyncTask
from app.rag.services.product_sync_tasks import process_next_product_sync_task


@pytest.mark.parametrize("scenario", ["empty", "success", "retry", "limit", "commit_failure"])
def test_processing_transaction_paths(scenario: str) -> None:
    # engine：隔离的内存数据库；rag_db：模拟的向量库会话
    engine = create_engine("sqlite://")
    rag_db = Mock(spec=Session)
    try:
        RagProductSyncTask.__table__.create(engine)
        if scenario != "empty":
            with Session(engine) as db:
                db.add(RagProductSyncTask(
                    id=5, product_id=123, operation="delete",
                    status="pending", retry_count=2 if scenario == "limit" else 0,
                    available_at=datetime.now() - timedelta(minutes=1),
                ))
                db.commit()

        started = datetime.now()
        with Session(engine) as db, patch(
            "app.rag.services.product_sync_tasks.execute_product_sync_task",
        ) as execute:
            def run_task(**kwargs):
                assert kwargs["mysql_db"] is db
                assert kwargs["rag_db"] is rag_db
                assert kwargs["task"].id == 5
                assert kwargs["task"].status == "processing"
                if scenario in {"retry", "limit"}:
                    raise RuntimeError("simulated provider failure")
            execute.side_effect = run_task
            if scenario == "commit_failure":
                with patch.object(db, "commit", side_effect=SQLAlchemyError("simulated commit failure")):
                    with pytest.raises(SQLAlchemyError):
                        process_next_product_sync_task(db, rag_db)
            else:
                assert process_next_product_sync_task(db, rag_db) is (scenario != "empty")
            if scenario == "empty":
                execute.assert_not_called()
            else:
                execute.assert_called_once()
            assert not db.in_transaction()

        with Session(engine) as db:
            task = db.get(RagProductSyncTask, 5)
            if scenario == "empty":
                assert task is None
            elif scenario == "success":
                assert task.status == "completed"
                assert task.completed_at >= started
                assert task.last_error is None
            elif scenario in {"retry", "limit"}:
                assert task.status == ("pending" if scenario == "retry" else "failed")
                assert task.retry_count == (1 if scenario == "retry" else 3)
                assert task.completed_at is None
                assert task.last_error == "RuntimeError"
                rag_db.rollback.assert_called_once_with()
                if scenario == "retry":
                    assert task.available_at >= started + timedelta(seconds=10)
            else:
                assert task.status == "pending"
                assert task.completed_at is None
                assert task.retry_count == 0
    finally:
        engine.dispose()


def test_failed_task_waits_then_recovers_on_next_attempt() -> None:
    """一次失败后保留任务，到期重试成功，且不调用真实AI服务。"""
    class TestClock(datetime):
        current = datetime(2026, 9, 21, 10)

        @classmethod
        def now(cls):
            return cls.current

    engine = create_engine("sqlite://")
    rag_db = Mock(spec=Session)
    try:
        RagProductSyncTask.__table__.create(engine)
        with Session(engine) as db:
            db.add(RagProductSyncTask(
                id=7, product_id=47, operation="upsert",
                status="pending", available_at=TestClock.current,
            ))
            db.commit()

        with (
            patch("app.rag.services.product_sync_tasks.datetime", TestClock),
            patch(
                "app.rag.services.product_sync_tasks.execute_product_sync_task",
                side_effect=[RuntimeError("simulated AI outage"), None],
            ) as execute,
        ):
            with Session(engine) as db:
                assert process_next_product_sync_task(db, rag_db) is True
                task = db.get(RagProductSyncTask, 7)
                assert task.status == "pending"
                assert task.retry_count == 1
                assert task.available_at == TestClock.current + timedelta(seconds=10)
                assert task.last_error == "RuntimeError"

            TestClock.current += timedelta(seconds=9)
            with Session(engine) as db:
                assert process_next_product_sync_task(db, rag_db) is False
            assert execute.call_count == 1

            TestClock.current += timedelta(seconds=1)
            with Session(engine) as db:
                assert process_next_product_sync_task(db, rag_db) is True
                task = db.get(RagProductSyncTask, 7)
                assert task.status == "completed"
                assert task.retry_count == 1
                assert task.last_error is None
                assert task.completed_at == TestClock.current
            assert execute.call_count == 2
    finally:
        engine.dispose()
