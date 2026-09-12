from unittest.mock import Mock

from app.mq.topology import (
    ORDER_EVENTS_EXCHANGE,
    ORDER_EXPIRATION_DELAY_KEY,
    ORDER_EXPIRATION_DELAY_QUEUE,
    ORDER_EXPIRATION_EXECUTE_KEY,
    ORDER_EXPIRATION_EXECUTE_QUEUE,
    ORDER_EXPIRATION_FAILED_KEY,
    ORDER_EXPIRATION_FAILED_QUEUE,
    ORDER_EXPIRATION_RETRY_KEY,
    ORDER_EXPIRATION_RETRY_QUEUE,
    ORDER_EXPIRATION_RETRY_TTL_MS,
    ORDER_EXPIRATION_TTL_MS,
    declare_order_topology,
)


def test_declare_order_topology_creates_delay_queue() -> None:
    channel = Mock()

    declare_order_topology(channel)

    channel.exchange_declare.assert_called_once_with(
        exchange=ORDER_EVENTS_EXCHANGE,
        exchange_type="direct",
        durable=True,
    )
    assert channel.queue_declare.call_count == 4
    channel.queue_declare.assert_any_call(
        queue=ORDER_EXPIRATION_DELAY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": ORDER_EXPIRATION_TTL_MS,
            "x-dead-letter-exchange": ORDER_EVENTS_EXCHANGE,
            "x-dead-letter-routing-key": (
                ORDER_EXPIRATION_EXECUTE_KEY
            ),
        },
    )
    channel.queue_declare.assert_any_call(
        queue=ORDER_EXPIRATION_EXECUTE_QUEUE,
        durable=True,
    )
    channel.queue_declare.assert_any_call(
        queue=ORDER_EXPIRATION_RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": ORDER_EXPIRATION_RETRY_TTL_MS,
            "x-dead-letter-exchange": ORDER_EVENTS_EXCHANGE,
            "x-dead-letter-routing-key": (
                ORDER_EXPIRATION_EXECUTE_KEY
            ),
        },
    )
    channel.queue_declare.assert_any_call(
        queue=ORDER_EXPIRATION_FAILED_QUEUE,
        durable=True,
    )

    assert channel.queue_bind.call_count == 4
    channel.queue_bind.assert_any_call(
        queue=ORDER_EXPIRATION_DELAY_QUEUE,
        exchange=ORDER_EVENTS_EXCHANGE,
        routing_key=ORDER_EXPIRATION_DELAY_KEY,
    )
    channel.queue_bind.assert_any_call(
        queue=ORDER_EXPIRATION_EXECUTE_QUEUE,
        exchange=ORDER_EVENTS_EXCHANGE,
        routing_key=ORDER_EXPIRATION_EXECUTE_KEY,
    )
    channel.queue_bind.assert_any_call(
        queue=ORDER_EXPIRATION_RETRY_QUEUE,
        exchange=ORDER_EVENTS_EXCHANGE,
        routing_key=ORDER_EXPIRATION_RETRY_KEY,
    )
    channel.queue_bind.assert_any_call(
        queue=ORDER_EXPIRATION_FAILED_QUEUE,
        exchange=ORDER_EVENTS_EXCHANGE,
        routing_key=ORDER_EXPIRATION_FAILED_KEY,
    )


def test_order_expiration_delay_is_thirty_minutes() -> None:
    assert ORDER_EXPIRATION_TTL_MS == 1_800_000


def test_order_expiration_retry_delay_is_ten_seconds() -> None:
    assert ORDER_EXPIRATION_RETRY_TTL_MS == 10_000
