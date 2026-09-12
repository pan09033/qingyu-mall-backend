import pika
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import engine
from app.exceptions import (
    ResourceNotFoundError,
    RetryableOrderExpirationError,
)
from app.mq.connection import create_rabbitmq_connection
from app.mq.messages import OrderExpirationMessage
from app.mq.topology import (
    ORDER_EVENTS_EXCHANGE,
    ORDER_EXPIRATION_EXECUTE_QUEUE,
    ORDER_EXPIRATION_FAILED_KEY,
    ORDER_EXPIRATION_RETRY_KEY,
    declare_order_topology,
)
from app.services.order import expire_pending_order


MAX_ORDER_EXPIRATION_RETRIES = 3


def get_retry_count(properties: pika.BasicProperties) -> int:
    headers = properties.headers or {}
    retry_count = headers.get("retry_count", 0)
    if (
        isinstance(retry_count, int)
        and not isinstance(retry_count, bool)
        and retry_count >= 0
    ):
        return retry_count
    return 0


def publish_processed_message(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    routing_key: str,
    body: bytes,
    retry_count: int,
) -> None:
    channel.basic_publish(
        exchange=ORDER_EVENTS_EXCHANGE,
        routing_key=routing_key,
        body=body,
        properties=pika.BasicProperties(
            content_type="application/json",
            content_encoding="utf-8",
            delivery_mode=pika.DeliveryMode.Persistent,
            headers={"retry_count": retry_count},
        ),
        mandatory=True,
    )


def process_order_expiration_message(body: bytes) -> None:
    message = OrderExpirationMessage.model_validate_json(body)

    with Session(engine) as db:
        expire_pending_order(db, message.order_id)


def handle_order_expiration(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    method: pika.spec.Basic.Deliver,
    properties: pika.BasicProperties,
    body: bytes,
) -> None:
    try:
        process_order_expiration_message(body)
    except RetryableOrderExpirationError:
        retry_count = get_retry_count(properties)
        if retry_count < MAX_ORDER_EXPIRATION_RETRIES:
            routing_key = ORDER_EXPIRATION_RETRY_KEY
            next_retry_count = retry_count + 1
        else:
            routing_key = ORDER_EXPIRATION_FAILED_KEY
            next_retry_count = retry_count

        publish_processed_message(
            channel,
            routing_key,
            body,
            next_retry_count,
        )
    except (ValidationError, ResourceNotFoundError):
        publish_processed_message(
            channel,
            ORDER_EXPIRATION_FAILED_KEY,
            body,
            get_retry_count(properties),
        )

    channel.basic_ack(delivery_tag=method.delivery_tag)


def run_order_expiration_worker() -> None:
    connection = create_rabbitmq_connection()

    try:
        channel = connection.channel()
        declare_order_topology(channel)
        channel.confirm_delivery()
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue=ORDER_EXPIRATION_EXECUTE_QUEUE,
            on_message_callback=handle_order_expiration,
            auto_ack=False,
        )
        channel.start_consuming()
    finally:
        if connection.is_open:
            connection.close()
