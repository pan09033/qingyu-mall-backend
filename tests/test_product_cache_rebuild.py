"""缓存重建分支测试：替代 Redis 和等待，不访问真实服务。"""

from unittest.mock import Mock, call
from threading import BoundedSemaphore, Event, Lock
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError

from app import product_cache
from app.exceptions import ResourceNotFoundError
from app.redis_client import redis_client
from app.schemas.product import ProductResponse
from app.services import product as service


@pytest.fixture
def product():
    return ProductResponse(id=2, name="测试商品", price=99, stock=5, category_id=1)


@pytest.fixture
def flow(monkeypatch):
    """隔离查询流程依赖，观察查库和释放锁的行为。"""
    mocks = {
        "get_cached_product": Mock(return_value=None),
        "try_acquire_product_cache_rebuild_lock": Mock(return_value=True),
        "wait_for_product_cache": Mock(return_value=None),
        "release_product_cache_rebuild_lock": Mock(return_value=True),
        "get_product_or_404": Mock(),
        "cache_product": Mock(),
        "cache_missing_product": Mock(),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(service, name, mock)
    return mocks


def test_double_check_returns_cache_and_releases_same_token(flow, product):
    """获得锁后已出现缓存，不再查库；提前返回也要释放自己的锁。"""
    flow["get_cached_product"].side_effect = [None, product]
    assert service.get_product_detail(Mock(), 2) is product
    flow["get_product_or_404"].assert_not_called()
    acquired = flow["try_acquire_product_cache_rebuild_lock"].call_args
    token = acquired.args[1]
    assert len(token) == 32
    flow["release_product_cache_rebuild_lock"].assert_called_once_with(2, token)


def test_waiter_returns_cache_without_releasing_lock(flow, product):
    """没抢到锁时复用等待结果，不查库、不释放别人的锁。"""
    flow["try_acquire_product_cache_rebuild_lock"].return_value = False
    flow["wait_for_product_cache"].return_value = product
    assert service.get_product_detail(Mock(), 2) is product
    flow["get_product_or_404"].assert_not_called()
    flow["release_product_cache_rebuild_lock"].assert_not_called()


def test_wait_timeout_falls_back_without_releasing_lock(flow, product):
    """等待结束后允许查库降级，但没有锁的请求不能释放锁。"""
    flow["try_acquire_product_cache_rebuild_lock"].return_value = False
    flow["get_product_or_404"].return_value = product
    flow["cache_product"].return_value = product
    db = Mock()
    assert service.get_product_detail(db, 2) is product
    flow["get_product_or_404"].assert_called_once_with(db, 2)
    flow["release_product_cache_rebuild_lock"].assert_not_called()


@pytest.mark.parametrize("missing", [True, False])
def test_query_exception_still_releases_lock(flow, missing):
    """404和意外查询异常都必须进入 finally，只有404才缓存空值。"""
    error = ResourceNotFoundError("商品不存在") if missing else RuntimeError("查询失败")
    flow["get_product_or_404"].side_effect = error
    with pytest.raises(type(error)):
        service.get_product_detail(Mock(), 2)
    flow["release_product_cache_rebuild_lock"].assert_called_once()
    assert flow["cache_missing_product"].call_count == int(missing)


def test_rebuild_writes_before_release(flow, product):
    """先写好商品缓存再释放锁，等待者才能读取结果。"""
    events = Mock()
    events.attach_mock(flow["cache_product"], "write")
    events.attach_mock(flow["release_product_cache_rebuild_lock"], "release")
    flow["get_product_or_404"].return_value = product
    flow["cache_product"].return_value = product
    assert service.get_product_detail(Mock(), 2) is product
    assert [item[0] for item in events.mock_calls] == ["write", "release"]


@pytest.mark.parametrize("appears", [True, False])
def test_wait_checks_same_product_and_stops(monkeypatch, product, appears):
    """始终查询同一商品；出现缓存就返回，否则在次数上限停止。"""
    read = Mock(side_effect=[None, product] if appears else [None, None, None])
    sleep = Mock()
    monkeypatch.setattr(product_cache, "get_cached_product", read)
    monkeypatch.setattr(product_cache.time, "sleep", sleep)
    monkeypatch.setattr(product_cache, "PRODUCT_CACHE_REBUILD_MAX_WAIT_ATTEMPTS", 3)
    result = product_cache.wait_for_product_cache(2)
    assert result is (product if appears else None)
    attempts = 2 if appears else 3
    assert read.call_args_list == [call(2)] * attempts
    assert sleep.call_args_list == [call(0.05)] * attempts


def test_release_uses_atomic_script_and_same_token(monkeypatch):
    """释放时通过 EVAL 传递锁 Key 和原 Token，不能直接 DEL。"""
    evaluate = Mock(return_value=1)
    delete = Mock()
    monkeypatch.setattr(redis_client, "eval", evaluate)
    monkeypatch.setattr(redis_client, "delete", delete)
    assert product_cache.release_product_cache_rebuild_lock(2, "token-a")
    evaluate.assert_called_once_with(
        product_cache.RELEASE_PRODUCT_CACHE_REBUILD_LOCK_SCRIPT,
        1, "lock:product:detail:2", "token-a",
    )
    delete.assert_not_called()


def test_release_failure_does_not_hide_product_result(monkeypatch, flow, product):
    """Redis 释放失败不会覆盖已查询到的商品结果。"""
    monkeypatch.setattr(redis_client, "eval", Mock(side_effect=RedisError("故障")))
    monkeypatch.setattr(service, "release_product_cache_rebuild_lock",
                        product_cache.release_product_cache_rebuild_lock)
    flow["get_product_or_404"].return_value = product
    flow["cache_product"].return_value = product
    assert service.get_product_detail(Mock(), 2) is product


@pytest.mark.parametrize("owns_lock", [True, False])
def test_full_db_slots_reject_without_query_or_extra_release(monkeypatch, flow, owns_lock):
    """名额已满返回503，不查库、不误还名额；持有的Redis锁仍释放。"""
    slots = BoundedSemaphore(1)
    assert slots.acquire(blocking=False)
    monkeypatch.setattr(service, "product_detail_db_slots", slots)
    flow["try_acquire_product_cache_rebuild_lock"].return_value = owns_lock
    with pytest.raises(HTTPException) as error:
        service.get_product_detail(Mock(), 2)
    assert error.value.status_code == 503
    flow["get_product_or_404"].assert_not_called()
    assert not slots.acquire(blocking=False)
    assert flow["release_product_cache_rebuild_lock"].call_count == int(owns_lock)
    slots.release()


@pytest.mark.parametrize("outcome", ["success", "missing", "error"])
def test_db_slot_returned_after_every_query(monkeypatch, flow, product, outcome):
    """正常、404和查询故障后名额都恢复，下一次查询仍可使用。"""
    slots = BoundedSemaphore(1)
    monkeypatch.setattr(service, "product_detail_db_slots", slots)

    def query(db, product_id):
        assert not slots.acquire(blocking=False)
        if outcome == "missing":
            raise ResourceNotFoundError("商品不存在")
        if outcome == "error":
            raise RuntimeError("查询故障")
        return product

    flow["get_product_or_404"].side_effect = query
    flow["cache_product"].return_value = product
    if outcome == "success":
        assert service.get_product_detail(Mock(), 2) is product
    else:
        expected = ResourceNotFoundError if outcome == "missing" else RuntimeError
        with pytest.raises(expected):
            service.get_product_detail(Mock(), 2)
    assert slots.acquire(blocking=False)
    assert not slots.acquire(blocking=False)
    slots.release()


@pytest.mark.parametrize("second_check", [False, True])
def test_cache_hit_needs_no_db_slot(monkeypatch, flow, product, second_check):
    """首次或二次检查命中缓存时，即使查库名额耗尽也能返回。"""
    slots = BoundedSemaphore(1)
    assert slots.acquire(blocking=False)
    monkeypatch.setattr(service, "product_detail_db_slots", slots)
    flow["get_cached_product"].side_effect = [None, product] if second_check else [product]
    assert service.get_product_detail(Mock(), 2) is product
    flow["get_product_or_404"].assert_not_called()
    assert not slots.acquire(blocking=False)
    slots.release()


def test_concurrent_queries_reject_overflow_and_recover(monkeypatch, flow, product):
    """两个真实线程占满测试名额，第三个被拒绝，结束后新查询恢复。"""
    # 仅测试替换为2个名额，正式配置仍为20。
    monkeypatch.setattr(service, "product_detail_db_slots", BoundedSemaphore(2))
    both_entered = Event()
    allow_finish = Event()
    counter_lock = Lock()
    entered_ids = []
    active = 0
    peak = 0

    def slow_query(db, product_id):
        nonlocal active, peak
        with counter_lock:
            entered_ids.append(product_id)
            active += 1
            peak = max(peak, active)
            if active == 2:
                both_entered.set()
        try:
            # 用事件确定执行顺序，不靠猜测sleep时长。
            assert allow_finish.wait(timeout=5), "测试未及时允许查询结束"
            return product
        finally:
            with counter_lock:
                active -= 1

    flow["get_product_or_404"].side_effect = slow_query
    flow["cache_product"].return_value = product

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.get_product_detail, Mock(), 101)
        second = pool.submit(service.get_product_detail, Mock(), 102)
        try:
            assert both_entered.wait(timeout=3), "两个查询未同时进入"
            with pytest.raises(HTTPException) as error:
                service.get_product_detail(Mock(), 103)
            assert error.value.status_code == 503
            with counter_lock:
                assert active == 2
                assert sorted(entered_ids) == [101, 102]
        finally:
            # 即使断言失败，也确保线程能结束。
            allow_finish.set()
        assert first.result(timeout=3) is product
        assert second.result(timeout=3) is product

    assert service.get_product_detail(Mock(), 104) is product
    assert sorted(entered_ids) == [101, 102, 104]
    assert active == 0
    assert peak == 2
