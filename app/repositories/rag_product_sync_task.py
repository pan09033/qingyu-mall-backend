from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rag_product_sync_task import RagProductSyncTask
from app.rag.sync_task_types import RagSyncTaskStatus


def add_product_sync_task(
    db: Session,
    task: RagProductSyncTask,
) -> None:
    """把商品同步任务加入当前会话，由Service统一提交。"""

    # db：商品业务正在使用的MySQL数据库会话
    # task：Service创建的商品同步任务对象
    db.add(task)


def get_next_pending_product_sync_task_for_update(
    db: Session,
    now: datetime,
) -> RagProductSyncTask | None:
    """查询并锁定一条到期的待处理任务，不提交事务。"""

    # db：MySQL数据库会话
    # now：调用方传入的当前时间
    # statement：待执行的查询语句
    statement = (
        select(RagProductSyncTask)
        .where(
            RagProductSyncTask.status == RagSyncTaskStatus.PENDING.value,
            RagProductSyncTask.available_at <= now,
        )
        .order_by(RagProductSyncTask.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    return db.scalar(statement)
