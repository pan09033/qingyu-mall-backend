from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.mq import publisher
from app.mq.topology import (
    ORDER_EVENTS_EXCHANGE,
    ORDER_EXPIRATION_DELAY_KEY,
)


def test_publish_order_expiration_sends_persistent_message(
    monkeypatch,
) -> None:
    connection = Mock()
    connection.is_open = True
    channel = connection.channel.return_value
    declare_topology = Mock()

    monkeypatch.setattr(
        publisher,
        "create_rabbitmq_connection",
        Mock(return_value=connection),
    )
    monkeypatch.setattr(
        publisher,
        "declare_order_topology",
        declare_topology,
    )

    publisher.publish_order_expiration(order_id=123)

    declare_topology.assert_called_once_with(channel)
    channel.confirm_delivery.assert_called_once_with()
    channel.basic_publish.assert_called_once()
    publish_arguments = channel.basic_publish.call_args.kwargs
    assert publish_arguments["exchange"] == ORDER_EVENTS_EXCHANGE
    assert (
        publish_arguments["routing_key"]
        == ORDER_EXPIRATION_DELAY_KEY
    )
    assert publish_arguments["body"] == b'{"order_id":123}'
    assert publish_arguments["mandatory"] is True

    properties = publish_arguments["properties"]
    assert properties.content_type == "application/json"
    assert properties.content_encoding == "utf-8"
    assert properties.delivery_mode == 2
    connection.close.assert_called_once_with()


def test_publish_order_expiration_closes_connection_on_error(
    monkeypatch,
) -> None:
    connection = Mock()
    connection.is_open = True
    channel = connection.channel.return_value
    channel.basic_publish.side_effect = RuntimeError(
        "publish failed"
    )

    monkeypatch.setattr(
        publisher,
        "create_rabbitmq_connection",
        Mock(return_value=connection),
    )

    with pytest.raises(RuntimeError, match="publish failed"):
        publisher.publish_order_expiration(order_id=123)

    connection.close.assert_called_once_with()


def test_publish_order_expiration_rejects_invalid_order_id(
    monkeypatch,
) -> None:
    connection_factory = Mock()
    monkeypatch.setattr(
        publisher,
        "create_rabbitmq_connection",
        connection_factory,
    )

    with pytest.raises(ValidationError):
        publisher.publish_order_expiration(order_id=0)

    connection_factory.assert_not_called()
