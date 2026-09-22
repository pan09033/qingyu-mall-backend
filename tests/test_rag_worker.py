from unittest.mock import MagicMock, Mock, call

import pytest

from app.rag import worker


@pytest.mark.parametrize("outcome", [True, False, RuntimeError("private diagnostic")])
def test_worker_loops_with_fresh_sessions_and_waits_when_needed(
    monkeypatch: pytest.MonkeyPatch, outcome: object,
) -> None:
    # contexts：模拟每轮两个数据库会话，不建立真实连接
    contexts = [MagicMock() for _ in range(4)]
    session = Mock(side_effect=contexts)
    process = Mock(side_effect=[outcome, KeyboardInterrupt()])
    sleep = Mock()
    logger = Mock()
    monkeypatch.setattr(worker, "Session", session)
    monkeypatch.setattr(worker, "process_next_product_sync_task", process)
    monkeypatch.setattr(worker.time, "sleep", sleep)
    monkeypatch.setattr(worker, "logger", logger)

    with pytest.raises(KeyboardInterrupt):
        worker.run_product_sync_worker()

    assert session.call_args_list == [
        call(worker.engine), call(worker.rag_engine),
        call(worker.engine), call(worker.rag_engine),
    ]
    assert process.call_args_list == [
        call(mysql_db=contexts[0].__enter__.return_value,
             rag_db=contexts[1].__enter__.return_value),
        call(mysql_db=contexts[2].__enter__.return_value,
             rag_db=contexts[3].__enter__.return_value),
    ]
    for context in contexts:
        context.__exit__.assert_called_once()
    if outcome is True:
        sleep.assert_not_called()
    else:
        sleep.assert_called_once_with(worker.POLL_INTERVAL_SECONDS)
    if isinstance(outcome, Exception):
        logger.error.assert_called_once_with(
            "商品知识同步本轮异常：%s", "RuntimeError",
        )
    else:
        logger.error.assert_not_called()
