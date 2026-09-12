import pytest
from pydantic import ValidationError

from app.mq.messages import OrderExpirationMessage


def test_order_expiration_message_accepts_positive_order_id() -> None:
    message = OrderExpirationMessage(order_id=123)

    assert message.order_id == 123
    assert message.model_dump_json() == '{"order_id":123}'


@pytest.mark.parametrize("order_id", [0, -1])
def test_order_expiration_message_rejects_non_positive_order_id(
    order_id: int,
) -> None:
    with pytest.raises(ValidationError):
        OrderExpirationMessage(order_id=order_id)


def test_order_expiration_message_requires_order_id() -> None:
    with pytest.raises(ValidationError):
        OrderExpirationMessage()
