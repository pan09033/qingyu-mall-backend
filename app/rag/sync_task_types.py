from enum import StrEnum


class ProductSyncOperation(StrEnum):
    """商品知识同步任务允许使用的操作。"""

    UPSERT = "upsert"
    # upsert：商品知识不存在就新增，已经存在就更新

    DELETE = "delete"
    # delete：删除商品对应的知识


class RagSyncTaskStatus(StrEnum):
    """RAG同步任务允许使用的状态。"""

    PENDING = "pending"
    # pending：等待处理

    PROCESSING = "processing"
    # processing：正在处理

    COMPLETED = "completed"
    # completed：处理成功

    FAILED = "failed"
    # failed：达到重试上限后仍然失败