from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.rag.services.product_sync import delete_product_knowledge


def test_delete_targets_only_requested_product_and_commits() -> None:
    db = Mock(spec=Session)
    delete_product_knowledge(db, 123)
    db.execute.assert_called_once()
    statement = db.execute.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "DELETE FROM knowledge_chunks" in sql
    assert "knowledge_chunks.source_type =" in sql
    assert "knowledge_chunks.source_id =" in sql
    assert " AND " in sql
    assert set(compiled.params.values()) == {"product", "123"}
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()


@pytest.mark.parametrize("failure_step", ["execute", "commit"])
def test_delete_rolls_back_and_propagates_database_error(failure_step: str) -> None:
    db = Mock(spec=Session)
    error = SQLAlchemyError("simulated database failure")
    getattr(db, failure_step).side_effect = error
    with pytest.raises(SQLAlchemyError) as caught:
        delete_product_knowledge(db, 123)
    assert caught.value is error
    db.rollback.assert_called_once_with()
    if failure_step == "execute":
        db.commit.assert_not_called()


@pytest.mark.parametrize("product_id", [0, -1])
def test_delete_rejects_invalid_id_before_database_access(product_id: int) -> None:
    db = Mock(spec=Session)
    with pytest.raises(ValueError, match="商品ID必须大于0"):
        delete_product_knowledge(db, product_id)
    db.execute.assert_not_called()
    db.commit.assert_not_called()
