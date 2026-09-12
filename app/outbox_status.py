from enum import StrEnum


class OutboxStatus(StrEnum):
    """数据库消息记录允许使用的状态。"""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
