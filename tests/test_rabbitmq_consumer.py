from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pika
import pytest

from app.exceptions import RetryableOrderExpirationError
from app.mq import consumer
from app.mq.topology import (
    ORDER_EVENTS_EXCHANGE,
    ORDER_EXPIRATION_EXECUTE_QUEUE,
    ORDER_EXPIRATION_FAILED_KEY,
    ORDER_EXPIRATION_RETRY_KEY,
)


def test_process_order_expiration_message_calls_service(
    monkeypatch,
) -> None:
    db = Mock()
    session_context = MagicMock()
    session_context.__enter__.return_value = db
    session_factory = Mock(return_value=session_context)
    expire_order = Mock()

    monkeypatch.setattr(consumer, "Session", session_factory)
    monkeypatch.setattr(
        consumer,
        "expire_pending_order",
        expire_order,
    )

    consumer.process_order_expiration_message(
        b'{"order_id":123}'
    )

    session_factory.assert_called_once_with(consumer.engine)
    expire_order.assert_called_once_with(db, 123)
    session_context.__exit__.assert_called_once()


def test_handle_order_expiration_acks_after_success(
    monkeypatch,
) -> None:
    channel = Mock()
    method = SimpleNamespace(delivery_tag=42)
    process_message = Mock()
    monkeypatch.setattr(
        consumer,
        "process_order_expiration_message",
        process_message,
    )

    consumer.handle_order_expiration(
        channel,
        method,
        Mock(),
        b'{"order_id":123}',
    )

    process_message.assert_called_once_with(b'{"order_id":123}')
    channel.basic_ack.assert_called_once_with(delivery_tag=42)


def test_handle_order_expiration_sends_first_retry(
    monkeypatch,
) -> None:
    channel = Mock()
    method = SimpleNamespace(delivery_tag=42)
    properties = pika.BasicProperties()
    monkeypatch.setattr(
        consumer,
        "process_order_expiration_message",
        Mock(side_effect=RetryableOrderExpirationError()),
    )

    consumer.handle_order_expiration(
        channel,
        method,
        properties,
        b'{"order_id":123}',
    )

    publish_arguments = channel.basic_publish.call_args.kwargs
    assert publish_arguments["exchange"] == ORDER_EVENTS_EXCHANGE
    assert publish_arguments["routing_key"] == (
        ORDER_EXPIRATION_RETRY_KEY
    )
    assert publish_arguments["properties"].headers == {
        "retry_count": 1,
    }
    channel.basic_ack.assert_called_once_with(delivery_tag=42)
    assert [call[0] for call in channel.method_calls] == [
        "basic_publish",
        "basic_ack",
    ]


def test_handle_order_expiration_sends_failed_after_max_retries(
    monkeypatch,
) -> None:
    channel = Mock()
    method = SimpleNamespace(delivery_tag=42)
    properties = pika.BasicProperties(
        headers={"retry_count": 3},
    )
    monkeypatch.setattr(
        consumer,
        "process_order_expiration_message",
        Mock(side_effect=RetryableOrderExpirationError()),
    )

    consumer.handle_order_expiration(
        channel,
        method,
        properties,
        b'{"order_id":123}',
    )

    publish_arguments = channel.basic_publish.call_args.kwargs
    assert publish_arguments["routing_key"] == (
        ORDER_EXPIRATION_FAILED_KEY
    )
    assert publish_arguments["properties"].headers == {
        "retry_count": 3,
    }
    channel.basic_ack.assert_called_once_with(delivery_tag=42)


def test_handle_order_expiration_does_not_ack_if_retry_publish_fails(
    monkeypatch,
) -> None:
    channel = Mock()
    channel.basic_publish.side_effect = RuntimeError(
        "publish failed"
    )
    method = SimpleNamespace(delivery_tag=42)
    properties = pika.BasicProperties()
    monkeypatch.setattr(
        consumer,
        "process_order_expiration_message",
        Mock(side_effect=RetryableOrderExpirationError()),
    )

    with pytest.raises(RuntimeError, match="publish failed"):
        consumer.handle_order_expiration(
            channel,
            method,
            properties,
            b'{"order_id":123}',
        )

    channel.basic_ack.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b'{"order_id":0}',
        b"{}",
    ],
)
def test_handle_order_expiration_sends_invalid_message_to_failed(
    body: bytes,
) -> None:
    channel = Mock()
    method = SimpleNamespace(delivery_tag=42)
    properties = pika.BasicProperties()

    consumer.handle_order_expiration(
        channel,
        method,
        properties,
        body,
    )

    publish_arguments = channel.basic_publish.call_args.kwargs
    assert publish_arguments["routing_key"] == (
        ORDER_EXPIRATION_FAILED_KEY
    )
    assert publish_arguments["body"] == body
    assert publish_arguments["properties"].headers == {
        "retry_count": 0,
    }
    channel.basic_ack.assert_called_once_with(delivery_tag=42)


def test_run_order_expiration_worker_listens_execute_queue(
    monkeypatch,
) -> None:
    connection = Mock()
    connection.is_open = True
    channel = connection.channel.return_value
    declare_topology = Mock()

    monkeypatch.setattr(
        consumer,
        "create_rabbitmq_connection",
        Mock(return_value=connection),
    )
    monkeypatch.setattr(
        consumer,
        "declare_order_topology",
        declare_topology,
    )

    consumer.run_order_expiration_worker()

    declare_topology.assert_called_once_with(channel)
    channel.confirm_delivery.assert_called_once_with()
    channel.basic_qos.assert_called_once_with(prefetch_count=1)
    channel.basic_consume.assert_called_once_with(
        queue=ORDER_EXPIRATION_EXECUTE_QUEUE,
        on_message_callback=consumer.handle_order_expiration,
        auto_ack=False,
    )
    channel.start_consuming.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_run_order_expiration_worker_closes_connection_on_error(
    monkeypatch,
) -> None:
    connection = Mock()
    connection.is_open = True
    channel = connection.channel.return_value
    channel.start_consuming.side_effect = RuntimeError(
        "consumer stopped"
    )
    monkeypatch.setattr(
        consumer,
        "create_rabbitmq_connection",
        Mock(return_value=connection),
    )

    with pytest.raises(RuntimeError, match="consumer stopped"):
        consumer.run_order_expiration_worker()

    connection.close.assert_called_once_with()
