from enum import StrEnum


class RefundType(StrEnum):
    """退款申请的业务类型。"""

    REFUND_ONLY = "refund_only"
    RETURN_AND_REFUND = "return_and_refund"
