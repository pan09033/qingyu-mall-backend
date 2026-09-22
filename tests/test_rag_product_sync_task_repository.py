from datetime import datetime, timedelta
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from app.models.rag_product_sync_task import RagProductSyncTask
from app.repositories.rag_product_sync_task import (
    get_next_pending_product_sync_task_for_update,
)


def test_selects_due_pending_tasks_in_id_order() -> None:
    # now：固定的测试时间；engine：临时内存数据库
    now = datetime(2026, 9, 20, 10)
    engine = create_engine("sqlite://")
    try:
        RagProductSyncTask.__table__.create(engine)
        with Session(engine) as db:
            assert get_next_pending_product_sync_task_for_update(db, now) is None
            for task_id, status, available_at in [
                (1, "pending", now + timedelta(seconds=1)),
                (2, "completed", now),
                (3, "processing", now),
                (4, "failed", now),
                (5, "pending", now),
                (6, "pending", now - timedelta(minutes=1)),
            ]:
                db.add(RagProductSyncTask(
                    id=task_id, product_id=123,
                    status=status, available_at=available_at,
                ))
            db.commit()
            task = get_next_pending_product_sync_task_for_update(db, now)
            assert task is not None and task.id == 5
            task.status = "processing"
            db.flush()
            next_task = get_next_pending_product_sync_task_for_update(db, now)
            assert next_task is not None and next_task.id == 6
            next_task.status = "processing"
            db.flush()
            assert get_next_pending_product_sync_task_for_update(db, now) is None
            db.rollback()
    finally:
        engine.dispose()


def test_query_requests_mysql_lock_without_committing() -> None:
    db = Mock(spec=Session)
    db.scalar.return_value = None
    assert get_next_pending_product_sync_task_for_update(
        db, datetime(2026, 9, 20, 10),
    ) is None
    statement = db.scalar.call_args.args[0]
    sql = str(statement.compile(dialect=mysql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "LIMIT" in sql
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
