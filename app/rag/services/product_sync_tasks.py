from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.rag_product_sync_task import RagProductSyncTask
from app.rag.sync_task_types import (
    ProductSyncOperation,
    RagSyncTaskStatus,
)
from app.rag.providers.factory import get_embedding_provider
from app.rag.repositories.product_source import (
    get_product_for_knowledge_sync,
)
from app.rag.services.product_sync import (
    delete_product_knowledge,
    sync_product_knowledge,
)

from app.repositories.rag_product_sync_task import (
    add_product_sync_task,
    get_next_pending_product_sync_task_for_update,
)


# 累计失败次数上限，包含首次执行失败
PRODUCT_SYNC_MAX_FAILURES = 3
# 重试等待时间，单位为秒
PRODUCT_SYNC_RETRY_DELAY_SECONDS = 10


def create_product_sync_task(
    db: Session,
    product_id: int,
    operation: ProductSyncOperation,
) -> RagProductSyncTask:
    """创建待处理任务，由调用方统一提交事务。"""

    # db：商品业务使用的MySQL会话
    # product_id：需要同步的商品ID
    # operation：新增或更新，或者删除
    if product_id <= 0:
        raise ValueError("商品ID必须大于0")

    # task：本次创建的同步任务对象
    task = RagProductSyncTask(
        product_id=product_id,
        operation=operation.value,
        status=RagSyncTaskStatus.PENDING.value,
    )

    add_product_sync_task(db, task)

    return task


def mark_product_sync_task_completed(
    task: RagProductSyncTask,
    completed_at: datetime,
) -> None:
    """更新任务对象的完成信息，由调用方提交。"""

    # task：本次处理的任务对象
    # completed_at：调用方传入的成功完成时间
    task.status = RagSyncTaskStatus.COMPLETED.value
    task.completed_at = completed_at

    # 重试成功后，清除上次失败的错误说明
    task.last_error = None


def schedule_product_sync_task_retry(
    task: RagProductSyncTask,
    error: Exception,
    now: datetime,
) -> None:
    """更新失败信息并安排重试，由调用方提交。"""

    # task：从数据库领取的任务，retry_count已有初始值
    # error：本次处理捕获的异常
    # now：本次失败的时间
    task.retry_count += 1
    task.completed_at = None

    # 只保存异常类型，避免原始异常携带连接凭据等信息
    task.last_error = type(error).__name__

    if task.retry_count >= PRODUCT_SYNC_MAX_FAILURES:
        task.status = RagSyncTaskStatus.FAILED.value
        return

    # 未到失败上限，重新进入等待状态
    task.status = RagSyncTaskStatus.PENDING.value
    task.available_at = now + timedelta(
        seconds=PRODUCT_SYNC_RETRY_DELAY_SECONDS,
    )


def execute_product_sync_task(
    mysql_db: Session,
    rag_db: Session,
    task: RagProductSyncTask,
) -> None:
    """根据任务操作，更新或删除商品知识。"""

    # mysql_db：读取商品的MySQL会话
    # rag_db：操作知识库的PostgreSQL会话
    # task：本次需要执行的任务

    if task.operation == ProductSyncOperation.DELETE.value:
        delete_product_knowledge(
            rag_db=rag_db,
            product_id=task.product_id,
        )
        return

    if task.operation != ProductSyncOperation.UPSERT.value:
        raise ValueError("不支持的商品同步操作")

    # product：从MySQL查询到的当前商品，也可能不存在
    product = get_product_for_knowledge_sync(
        mysql_db=mysql_db,
        product_id=task.product_id,
    )

    if product is None:
        # 任务创建后商品可能已被删除，清理残留知识
        delete_product_knowledge(
            rag_db=rag_db,
            product_id=task.product_id,
        )
        return

    # embedding_provider：需要生成向量时才获取BGE
    embedding_provider = get_embedding_provider()

    sync_product_knowledge(
        rag_db=rag_db,
        product=product,
        embedding_provider=embedding_provider,
    )


def process_next_product_sync_task(
    mysql_db: Session,
    rag_db: Session,
) -> bool:
    """处理一条到期任务；没有任务时返回False。"""

    try:
        # task：查询并锁住的任务对象
        task = get_next_pending_product_sync_task_for_update(
            db=mysql_db,
            now=datetime.now(),
        )

        if task is None:
            # 查询也会开启事务，结束它以释放资源
            mysql_db.rollback()
            return False

        task.status = RagSyncTaskStatus.PROCESSING.value

        try:
            # 把查询到的task交给执行函数
            execute_product_sync_task(
                mysql_db=mysql_db,
                rag_db=rag_db,
                task=task,
            )

        except Exception as error:
            # 清理本次未提交的向量库操作
            rag_db.rollback()

            # MySQL会话若已因失败而无法继续，交给外层回滚
            if not mysql_db.is_active:
                raise

            schedule_product_sync_task_retry(
                task=task,
                error=error,
                now=datetime.now(),
            )

        else:
            # 只有执行成功，才标记完成
            mark_product_sync_task_completed(
                task=task,
                completed_at=datetime.now(),
            )

        # 保存完成状态，或失败后的重试安排，并释放任务行锁
        mysql_db.commit()
        return True

    except Exception:
        # 查询任务或保存任务结果失败时，回滚MySQL事务
        mysql_db.rollback()
        raise
