from enum import StrEnum


class RefundStatus(StrEnum):
    """退款申请允许使用的状态。"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
