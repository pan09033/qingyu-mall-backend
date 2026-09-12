from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import RetryableOrderExpirationError
from app.services import order as order_service


def test_expire_pending_order_wraps_database_error(
    monkeypatch,
) -> None:
    db = Mock()
    monkeypatch.setattr(
        order_service,
        "get_order_by_id_for_update",
        Mock(side_effect=SQLAlchemyError("database unavailable")),
    )

    with pytest.raises(
        RetryableOrderExpirationError,
        match="订单过期处理遇到数据库故障",
    ):
        order_service.expire_pending_order(db, order_id=123)

    db.rollback.assert_called_once_with()
