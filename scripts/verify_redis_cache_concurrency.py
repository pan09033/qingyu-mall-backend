"""本机真实Redis并发验证；在项目根目录用 python -m scripts.verify_redis_cache_concurrency 运行。

真实执行SET NX EX、GET、SET和Lua；仅数据库查询为模拟函数。
独立随机Key前缀，所有测试Key都有TTL，退出时只清理本次Key。
无需启动FastAPI或连接MySQL，不输出配置或密码。
"""

import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from threading import Barrier, Lock
from unittest.mock import patch
from uuid import uuid4


def verify():
    # 在入口内部加载配置，失败时由main输出脱敏错误。
    from app import product_cache as cache
    from app.redis_client import redis_client
    from app.schemas.product import ProductResponse
    from app.services import product as service

    redis_client.ping()
    print("Redis连接成功；真实Redis + 6个线程 + 模拟数据库查询。")
    prefix = f"practice:cache_concurrency:{uuid4().hex}"
    keys = [f"{prefix}:product:2", f"{prefix}:lock:2"]
    product = ProductResponse(
        id=2, name="并发验证商品", price=99, stock=5, category_id=1,
    )
    try:
        with ExitStack() as stack:
            # 只在此独立脚本进程内替换Key生成，不修改项目源文件。
            stack.enter_context(patch.object(cache, "product_detail_cache_key", lambda _id: keys[0]))
            stack.enter_context(patch.object(cache, "product_cache_rebuild_lock_key", lambda _id: keys[1]))
            barrier = Barrier(6, timeout=5)
            counter_lock = Lock()
            query_count = 0
            winners = 0
            acquire = service.try_acquire_product_cache_rebuild_lock

            def counted_acquire(product_id, token):
                nonlocal winners
                # 六个线程都已首次缓存未命中，再一起尝试真实Redis抢锁。
                barrier.wait()
                result = acquire(product_id, token)
                with counter_lock:
                    winners += int(result)
                return result

            def simulated_query(db, product_id):
                nonlocal query_count
                with counter_lock:
                    query_count += 1
                time.sleep(0.2)
                return product

            with patch.object(service, "try_acquire_product_cache_rebuild_lock", counted_acquire), \
                 patch.object(service, "get_product_or_404", simulated_query):
                with ThreadPoolExecutor(max_workers=6) as pool:
                    futures = [pool.submit(service.get_product_detail, None, 2) for _ in range(6)]
                    results = [future.result(timeout=10) for future in futures]

            assert all(result.id == 2 and result.name == product.name for result in results)
            assert winners == 1, f"预期1次获锁，实际{winners}"
            assert query_count == 1, f"预期1次查库，实际{query_count}"
            assert redis_client.get(keys[0]) is not None
            assert 0 < redis_client.ttl(keys[0]) <= 360
            assert redis_client.get(keys[1]) is None
            print(f"PASS：6次并发调用全部返回商品；获锁{winners}次，模拟查库{query_count}次。")
            print("PASS：商品缓存已写入且有TTL，重建锁已释放。")

            # 真实Lua验证：错误Token不能删除锁，正确Token可以删除。
            assert cache.try_acquire_product_cache_rebuild_lock(2, "owner-a")
            assert not cache.release_product_cache_rebuild_lock(2, "other-b")
            assert redis_client.get(keys[1]) == "owner-a"
            assert cache.release_product_cache_rebuild_lock(2, "owner-a")
            assert redis_client.get(keys[1]) is None
            print("PASS：真实Lua拒绝错误Token，允许原Token释放锁。")

            # 在测试Key上缩短租期，观察过期后旧持有者不能删除新锁。
            assert cache.try_acquire_product_cache_rebuild_lock(2, "expired-a")
            assert redis_client.pexpire(keys[1], 100)
            deadline = time.monotonic() + 3
            while redis_client.exists(keys[1]):
                assert time.monotonic() < deadline, "测试锁未按期过期"
                time.sleep(0.02)
            assert cache.try_acquire_product_cache_rebuild_lock(2, "new-b")
            assert not cache.release_product_cache_rebuild_lock(2, "expired-a")
            assert redis_client.get(keys[1]) == "new-b"
            assert cache.release_product_cache_rebuild_lock(2, "new-b")
            print("PASS：旧锁过期后，旧Token不能误删新持有者的锁。")

            # 清除本次商品缓存，让查询异常路径真实获取并释放Redis锁。
            redis_client.delete(keys[0])
            class SimulatedQueryError(Exception):
                pass

            with patch.object(service, "get_product_or_404", side_effect=SimulatedQueryError):
                try:
                    service.get_product_detail(None, 2)
                except SimulatedQueryError:
                    pass
                else:
                    raise AssertionError("未传播模拟查询异常")
            assert redis_client.get(keys[1]) is None
            print("PASS：查询异常后finally释放了真实Redis锁。")
    finally:
        try:
            removed = redis_client.delete(*keys)
            print(f"清理完成：删除本次临时Key {removed}个；未操作业务Key。")
        except Exception:
            print("临时Key清理失败，将按自身TTL过期。")
            raise


def main():
    try:
        verify()
    except Exception as error:
        # Redis旧版本的认证错误可能带敏感参数，不输出异常原文或堆栈。
        print(f"验证失败（{type(error).__name__}）；请在本机检查Redis连接、配置及上方通过步骤。")
        return 1
    print("验证完成。这是单进程服务层并发验证，不是HTTP压测或多进程容量验证。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
