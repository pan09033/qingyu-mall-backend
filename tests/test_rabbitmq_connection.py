from types import SimpleNamespace
from unittest.mock import Mock

from app.mq import connection as rabbitmq_connection


def test_create_rabbitmq_connection_uses_settings(
    monkeypatch,
) -> None:
    fake_settings = SimpleNamespace(
        rabbitmq_host="rabbitmq.test",
        rabbitmq_port=5673,
        rabbitmq_username="test-user",
        rabbitmq_password="test-password",
        rabbitmq_virtual_host="test-vhost",
    )
    fake_credentials = object()
    fake_parameters = object()
    fake_connection = object()

    credentials_factory = Mock(
        return_value=fake_credentials,
    )
    parameters_factory = Mock(
        return_value=fake_parameters,
    )
    connection_factory = Mock(
        return_value=fake_connection,
    )

    monkeypatch.setattr(
        rabbitmq_connection,
        "settings",
        fake_settings,
    )
    monkeypatch.setattr(
        rabbitmq_connection.pika,
        "PlainCredentials",
        credentials_factory,
    )
    monkeypatch.setattr(
        rabbitmq_connection.pika,
        "ConnectionParameters",
        parameters_factory,
    )
    monkeypatch.setattr(
        rabbitmq_connection.pika,
        "BlockingConnection",
        connection_factory,
    )

    result = rabbitmq_connection.create_rabbitmq_connection()

    credentials_factory.assert_called_once_with(
        username="test-user",
        password="test-password",
    )
    parameters_factory.assert_called_once_with(
        host="rabbitmq.test",
        port=5673,
        virtual_host="test-vhost",
        credentials=fake_credentials,
    )
    connection_factory.assert_called_once_with(
        fake_parameters,
    )
    assert result is fake_connection
