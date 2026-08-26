from enum import StrEnum


class PaymentStatus(StrEnum):
    """支付记录允许使用的状态。"""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
