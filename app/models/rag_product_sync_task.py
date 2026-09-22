from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.rag.sync_task_types import (
    ProductSyncOperation,
    RagSyncTaskStatus,
)


class RagProductSyncTask(Base):
    """保存在MySQL中的商品知识同步任务。"""

    __tablename__ = "rag_product_sync_tasks"

    # __table_args__：数据库表的约束等配置
    __table_args__ = (
        CheckConstraint(
            "product_id > 0",
            name="ck_rag_product_sync_tasks_product_id_positive",
        ),
        CheckConstraint(
            "operation IN ('upsert', 'delete')",
            name="ck_rag_product_sync_tasks_operation_allowed",
        ),
        CheckConstraint(
            "status IN "
            "('pending', 'processing', 'completed', 'failed')",
            name="ck_rag_product_sync_tasks_status_allowed",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_rag_product_sync_tasks_retry_nonnegative",
        ),
        # 联合索引：帮助按任务状态和可执行时间查找任务
        Index(
            "ix_rag_product_sync_tasks_status_available_at",
            "status",
            "available_at",
        ),
    )

    # id：任务自身的编号
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # product_id：需要处理的商品编号
    product_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # operation：新增或更新知识，或者删除知识
    operation: Mapped[str] = mapped_column(
        String(20),
        default=ProductSyncOperation.UPSERT.value,
        nullable=False,
    )

    # status：任务当前状态，初始为等待处理
    status: Mapped[str] = mapped_column(
        String(20),
        default=RagSyncTaskStatus.PENDING.value,
        server_default=RagSyncTaskStatus.PENDING.value,
        nullable=False,
    )

    # retry_count：失败重试计数，初始为0
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    # available_at：允许执行任务的时间，初始为插入时刻
    available_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    # last_error：上次失败原因，尚未失败时可以为空
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # created_at：任务创建时间，由数据库自动填写
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    # completed_at：任务成功完成的时间，初始为空
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
