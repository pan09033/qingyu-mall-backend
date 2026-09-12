import pika

from app.config import settings


def create_rabbitmq_connection() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(
        username=settings.rabbitmq_username,
        password=settings.rabbitmq_password,
    )

    parameters = pika.ConnectionParameters(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        virtual_host=settings.rabbitmq_virtual_host,
        credentials=credentials,
    )

    return pika.BlockingConnection(parameters)