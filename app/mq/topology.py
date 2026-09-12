from pika.adapters.blocking_connection import BlockingChannel


ORDER_EVENTS_EXCHANGE = "order.events"
ORDER_EXPIRATION_DELAY_QUEUE = "order.expiration.delay"
ORDER_EXPIRATION_DELAY_KEY = "order.expiration.delay"
ORDER_EXPIRATION_EXECUTE_QUEUE = "order.expiration.execute"
ORDER_EXPIRATION_EXECUTE_KEY = "order.expiration.execute"
ORDER_EXPIRATION_RETRY_QUEUE = "order.expiration.retry"
ORDER_EXPIRATION_RETRY_KEY = "order.expiration.retry"
ORDER_EXPIRATION_FAILED_QUEUE = "order.expiration.failed"
ORDER_EXPIRATION_FAILED_KEY = "order.expiration.failed"
ORDER_EXPIRATION_TTL_MS = 30 * 60 * 1000
ORDER_EXPIRATION_RETRY_TTL_MS = 10 * 1000


def declare_order_topology(
    channel: BlockingChannel,
) -> None:
    channel.exchange_declare(
        exchange=ORDER_EVENTS_EXCHANGE,
        exchange_type="direct",
        durable=True,
    )

    channel.queue_declare(
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

    channel.queue_bind(
        queue=ORDER_EXPIRATION_DELAY_QUEUE,
        exchange=ORDER_EVENTS_EXCHANGE,
        routing_key=ORDER_EXPIRATION_DELAY_KEY,
    )

    channel.queue_declare(
        queue=ORDER_EXPIRATION_EXECUTE_QUEUE,
        durable=True,
    )

    channel.queue_bind(
        queue=ORDER_EXPIRATION_EXECUTE_QUEUE,
        exchange=ORDER_EVENTS_EXCHANGE,
        routing_key=ORDER_EXPIRATION_EXECUTE_KEY,
    )

    channel.queue_declare(
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

    channel.queue_bind(
        queue=ORDER_EXPIRATION_RETRY_QUEUE,
        exchange=ORDER_EVENTS_EXCHANGE,
        routing_key=ORDER_EXPIRATION_RETRY_KEY,
    )

    channel.queue_declare(
        queue=ORDER_EXPIRATION_FAILED_QUEUE,
        durable=True,
    )

    channel.queue_bind(
        queue=ORDER_EXPIRATION_FAILED_QUEUE,
        exchange=ORDER_EVENTS_EXCHANGE,
        routing_key=ORDER_EXPIRATION_FAILED_KEY,
    )
