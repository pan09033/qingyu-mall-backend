from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from pika.exceptions import AMQPError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.outbox_message import OutboxMessage
from app.outbox_status import OutboxStatus
from app.services import outbox as outbox_service


def make_outbox_message(
    retry_count: int = 0,
) -> OutboxMessage:
    return OutboxMessage(
        id=1,
        order_id=123,
        event_type="order.expiration",
        payload={"order_id": 123},
        status=OutboxStatus.PENDING,
        retry_count=retry_count,
    )


def test_publish_next_outbox_message_marks_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RabbitMQ 确认收到后，数据库消息应标记为已发送。"""

    db = Mock(spec=Session)
    message = make_outbox_message()
    publish = Mock()
    now = datetime(2026, 9, 6, 12, 0, 0)
    monkeypatch.setattr(
        outbox_service,
        "get_next_pending_outbox_message_for_update",
        lambda *_args: message,
    )
    monkeypatch.setattr(
        outbox_service,
        "publish_order_expiration",
        publish,
    )

    processed = outbox_service.publish_next_outbox_message(
        db,
        now,
    )

    assert processed is True
    publish.assert_called_once_with(123)
    assert message.status == OutboxStatus.SENT
    assert message.sent_at == now
    assert message.last_error is None
    db.commit.assert_called_once_with()


def test_publish_next_outbox_message_schedules_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """临时发送失败时保留消息，并延后下一次尝试。"""

    db = Mock(spec=Session)
    message = make_outbox_message()
    now = datetime(2026, 9, 6, 12, 0, 0)
    monkeypatch.setattr(
        outbox_service,
        "get_next_pending_outbox_message_for_update",
        lambda *_args: message,
    )
    monkeypatch.setattr(
        outbox_service,
        "publish_order_expiration",
        Mock(side_effect=AMQPError("broker unavailable")),
    )

    processed = outbox_service.publish_next_outbox_message(
        db,
        now,
    )

    assert processed is True
    assert message.status == OutboxStatus.PENDING
    assert message.retry_count == 1
    assert message.available_at == now + timedelta(seconds=10)
    assert "broker unavailable" in message.last_error
    db.commit.assert_called_once_with()


def test_publish_next_outbox_message_stops_after_retry_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第三次发送仍失败时，应停止自动重试并标记为失败。"""

    db = Mock(spec=Session)
    message = make_outbox_message(retry_count=2)
    monkeypatch.setattr(
        outbox_service,
        "get_next_pending_outbox_message_for_update",
        lambda *_args: message,
    )
    monkeypatch.setattr(
        outbox_service,
        "publish_order_expiration",
        Mock(side_effect=AMQPError("broker unavailable")),
    )

    processed = outbox_service.publish_next_outbox_message(db)

    assert processed is True
    assert message.retry_count == 3
    assert message.status == OutboxStatus.FAILED
    db.commit.assert_called_once_with()


def test_publish_next_outbox_message_rejects_invalid_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """数据库消息内容错误时不应发送，而应保留失败记录。"""

    db = Mock(spec=Session)
    message = make_outbox_message()
    message.payload = {"order_id": -1}
    publish = Mock()
    monkeypatch.setattr(
        outbox_service,
        "get_next_pending_outbox_message_for_update",
        lambda *_args: message,
    )
    monkeypatch.setattr(
        outbox_service,
        "publish_order_expiration",
        publish,
    )

    processed = outbox_service.publish_next_outbox_message(db)

    assert processed is True
    publish.assert_not_called()
    assert message.status == OutboxStatus.FAILED
    assert message.last_error is not None
    db.commit.assert_called_once_with()


def test_publish_next_outbox_message_returns_false_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """没有待发送消息时结束当前事务并等待下一轮。"""

    db = Mock(spec=Session)
    monkeypatch.setattr(
        outbox_service,
        "get_next_pending_outbox_message_for_update",
        lambda *_args: None,
    )

    processed = outbox_service.publish_next_outbox_message(db)

    assert processed is False
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_publish_next_outbox_message_rolls_back_database_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """数据库异常时回滚，并交给 Worker 下一轮重试。"""

    db = Mock(spec=Session)
    monkeypatch.setattr(
        outbox_service,
        "get_next_pending_outbox_message_for_update",
        Mock(side_effect=SQLAlchemyError("database unavailable")),
    )

    with pytest.raises(SQLAlchemyError):
        outbox_service.publish_next_outbox_message(db)

    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()
