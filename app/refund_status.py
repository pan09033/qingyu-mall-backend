from enum import StrEnum


class RefundStatus(StrEnum):
    """退款申请允许使用的状态。"""

    PENDING = "pending"
    WAITING_RETURN = "waiting_return"
    RETURNING = "returning"
    APPROVED = "approved"
    REJECTED = "rejected"
