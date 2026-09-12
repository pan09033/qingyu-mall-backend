import pika

from app.mq.connection import create_rabbitmq_connection
from app.mq.messages import OrderExpirationMessage
from app.mq.topology import (
    ORDER_EVENTS_EXCHANGE,
    ORDER_EXPIRATION_DELAY_KEY,
    declare_order_topology,
)


def publish_order_expiration(order_id: int) -> None:
    message = OrderExpirationMessage(order_id=order_id)
    body = message.model_dump_json().encode("utf-8")
    connection = create_rabbitmq_connection()

    try:
        channel = connection.channel()
        declare_order_topology(channel)
        channel.confirm_delivery()
        channel.basic_publish(
            exchange=ORDER_EVENTS_EXCHANGE,
            routing_key=ORDER_EXPIRATION_DELAY_KEY,
            body=body,
            properties=pika.BasicProperties(
                content_type="application/json",
                content_encoding="utf-8",
                delivery_mode=pika.DeliveryMode.Persistent,
            ),
            mandatory=True,
        )
    finally:
        if connection.is_open:
            connection.close()
