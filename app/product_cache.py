"""商品详情缓存的统一读写与失效逻辑。"""

import logging
import random
import time
from collections.abc import Iterable

from pydantic import ValidationError
from redis.exceptions import RedisError

from app.exceptions import ResourceNotFoundError
from app.redis_client import redis_client
from app.schemas.product import ProductResponse

logger = logging.getLogger(__name__)

# 正常商品缓存基础时间300秒，写入时再增加随机偏移。
PRODUCT_DETAIL_CACHE_TTL_SECONDS = 300

# 正常商品缓存额外增加0～60秒，减少集中到期。
PRODUCT_DETAIL_CACHE_TTL_JITTER_SECONDS = 60

# 商品不存在时写入 Redis 的特殊标记，以及标记的保存时间。
PRODUCT_NOT_FOUND_CACHE_VALUE = "__product_not_found__"
PRODUCT_NOT_FOUND_CACHE_TTL_SECONDS = 60

# 商品缓存重建锁最多保存5秒，防止请求异常后锁一直存在。
PRODUCT_CACHE_REBUILD_LOCK_TTL_SECONDS = 5

# 未获得锁时，每50毫秒检查一次商品缓存，最多检查20次。
PRODUCT_CACHE_REBUILD_WAIT_INTERVAL_SECONDS = 0.05
PRODUCT_CACHE_REBUILD_MAX_WAIT_ATTEMPTS = 20

# 只有锁的 Value 属于当前请求时，才允许删除锁。
RELEASE_PRODUCT_CACHE_REBUILD_LOCK_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
end

return 0
"""


# 根据商品 ID 生成商品缓存重建锁的 Redis Key。
def product_cache_rebuild_lock_key(
    product_id: int,
) -> str:
    return f"lock:product:detail:{product_id}"


# 尝试获得商品缓存重建锁，成功返回 True。
def try_acquire_product_cache_rebuild_lock(
    product_id: int,
    lock_token: str,
) -> bool:
    try:
        lock_result = redis_client.set(
            product_cache_rebuild_lock_key(product_id),
            lock_token,
            nx=True,
            ex=PRODUCT_CACHE_REBUILD_LOCK_TTL_SECONDS,
        )
    except RedisError:
        logger.warning(
            "获取商品缓存重建锁失败：product_id=%s",
            product_id,
        )
        return False

    return bool(lock_result)


# 只释放属于当前请求的商品缓存重建锁。
def release_product_cache_rebuild_lock(
    product_id: int,
    lock_token: str,
) -> bool:
    try:
        release_result = redis_client.eval(
            RELEASE_PRODUCT_CACHE_REBUILD_LOCK_SCRIPT,
            1,
            product_cache_rebuild_lock_key(product_id),
            lock_token,
        )
    except RedisError:
        logger.warning(
            "释放商品缓存重建锁失败：product_id=%s",
            product_id,
        )
        return False

    return bool(release_result)

# 根据商品 ID 生成统一的 Redis Key。
def product_detail_cache_key(product_id: int) -> str:
    """返回商品详情缓存 Key。"""

    return f"product:detail:{product_id}"


# 从 Redis 读取商品缓存，并把 JSON 转换为商品响应模型。
def get_cached_product(
    product_id: int,
) -> ProductResponse | None:
    """读取并校验缓存；缓存不可用或损坏时返回 ``None``。"""

    cache_key = product_detail_cache_key(product_id)
    try:
        cached_product = redis_client.get(cache_key)
    except RedisError:
        logger.warning(
            "读取商品缓存失败，回退到数据库：product_id=%s",
            product_id,
        )
        return None

    if cached_product is None:
        return None

    if cached_product == PRODUCT_NOT_FOUND_CACHE_VALUE:
        raise ResourceNotFoundError(
            "商品不存在"
        )

    try:
        return ProductResponse.model_validate_json(cached_product)
    except (ValidationError, ValueError, TypeError):
        logger.warning(
            "商品缓存内容无效，回退到数据库：product_id=%s",
            product_id,
        )
        invalidate_product_cache([product_id])
        return None


# 短暂等待其他请求完成商品缓存重建。
def wait_for_product_cache(
    product_id: int,
) -> ProductResponse | None:
    for _ in range(PRODUCT_CACHE_REBUILD_MAX_WAIT_ATTEMPTS):
        time.sleep(PRODUCT_CACHE_REBUILD_WAIT_INTERVAL_SECONDS)

        cached_product = get_cached_product(
            product_id
        )
        if cached_product is not None:
            return cached_product

    return None


# 把“商品不存在”标记写入 Redis，减少重复查询 MySQL。
def cache_missing_product(product_id: int) -> None:
    try:
        redis_client.set(
            product_detail_cache_key(product_id),
            PRODUCT_NOT_FOUND_CACHE_VALUE,
            ex=PRODUCT_NOT_FOUND_CACHE_TTL_SECONDS,
        )
    except RedisError:
        logger.warning(
            "写入商品空值缓存失败：product_id=%s",
            product_id,
        )


# 把从 MySQL 查询到的商品转换成 JSON，并写入 Redis。
def cache_product(product: object) -> ProductResponse:
    """缓存商品详情；Redis 故障不影响数据库查询结果。"""

    response = ProductResponse.model_validate(product)
    # 每次写入商品缓存时，重新生成过期时间。
    cache_ttl = PRODUCT_DETAIL_CACHE_TTL_SECONDS + random.randint(
        0,
        PRODUCT_DETAIL_CACHE_TTL_JITTER_SECONDS,
    )
    try:
        redis_client.set(
            product_detail_cache_key(response.id),
            response.model_dump_json(),
            ex=cache_ttl,
        )
    except RedisError:
        logger.warning(
            "写入商品缓存失败，直接返回数据库结果：product_id=%s",
            response.id,
        )

    return response


# 商品发生变化后，删除对应的 Redis 缓存，防止读取旧数据。
def invalidate_product_cache(
    product_ids: Iterable[int],
) -> None:
    """批量删除商品详情缓存；Redis 故障不回滚已提交的业务事务。"""

    unique_product_ids = sorted(set(product_ids))
    cache_keys = [
        product_detail_cache_key(product_id)
        for product_id in unique_product_ids
    ]
    if not cache_keys:
        return

    try:
        redis_client.delete(*cache_keys)
    except RedisError:
        logger.warning(
            "商品缓存失效失败，等待 TTL 过期：product_ids=%s",
            unique_product_ids,
        )
