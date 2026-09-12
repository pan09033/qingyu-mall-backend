import logging
from hashlib import sha256

from fastapi import HTTPException, status
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import redis_client


logger = logging.getLogger(__name__)


RECORD_LOGIN_FAILURE_SCRIPT = """
local existing_lock_level = tonumber(
    redis.call("GET", KEYS[3]) or "0"
)

if existing_lock_level > 0 then
    local new_lock_level = redis.call(
        "INCR",
        KEYS[3]
    )
    redis.call(
        "EXPIRE",
        KEYS[3],
        ARGV[3]
    )
    local duration_index = math.min(
        new_lock_level,
        3
    )

    local lock_seconds = tonumber(
        ARGV[3 + duration_index]
    )
    redis.call(
        "SET",
        KEYS[2],
        tostring(new_lock_level),
        "EX",
        lock_seconds
    )
    redis.call(
        "DEL",
        KEYS[1]
    )
    return new_lock_level
end

local new_fail_count = redis.call(
    "INCR",
    KEYS[1]
)

if new_fail_count == 1 then
    redis.call(
        "EXPIRE",
        KEYS[1],
        ARGV[2]
    )
end

if new_fail_count < tonumber(ARGV[1]) then
    return 0
end

local new_lock_level = redis.call(
    "INCR",
    KEYS[3]
)

redis.call(
    "EXPIRE",
    KEYS[3],
    ARGV[3]
)
redis.call(
    "SET",
    KEYS[2],
    tostring(new_lock_level),
    "EX",
    ARGV[4]
)
redis.call(
    "DEL",
    KEYS[1]
)
return new_lock_level
"""


def build_login_rate_limit_scope(
    client_ip: str,
    username: str,
) -> str:
    """生成不暴露用户名的稳定限流作用域。"""

    normalized_username = username.strip().lower()
    identity = f"{client_ip}\0{normalized_username}"
    return sha256(identity.encode("utf-8")).hexdigest()


def _failure_key(
    scope: str,
) -> str:
    """生成登录失败计数 Key。"""

    return f"rate_limit:login:fail:{scope}"


def _lock_key(
    scope: str,
) -> str:
    """生成登录锁定状态 Key。"""

    return f"rate_limit:login:lock:{scope}"


def _lock_level_key(
    scope: str,
) -> str:
    """生成登录锁定等级 Key。"""

    return f"rate_limit:login:level:{scope}"


def check_login_rate_limit(
    scope: str,
) -> None:
    """检查客户端当前是否处于登录锁定状态。"""

    lock_key = _lock_key(scope)

    try:
        lock_value = redis_client.get(
            lock_key
        )
    except RedisError:
        logger.warning(
            "读取登录锁定状态失败，暂时跳过限流"
        )
        return

    if lock_value is None:
        return

    try:
        retry_after = redis_client.ttl(
            lock_key
        )
    except RedisError:
        logger.warning(
            "读取登录锁定剩余时间失败，使用默认时间"
        )
        retry_after = (
            settings.login_lock_durations_seconds[0]
        )

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="登录失败次数过多，请稍后再试",
        headers={
            "Retry-After": str(
                max(retry_after, 0)
            ),
        },
    )


def record_login_failure(
    scope: str,
) -> None:
    """以原子方式记录登录失败并按需创建锁。"""

    failure_key = _failure_key(scope)
    lock_key = _lock_key(scope)
    level_key = _lock_level_key(scope)

    try:
        redis_client.eval(
            RECORD_LOGIN_FAILURE_SCRIPT,
            3,
            failure_key,
            lock_key,
            level_key,
            settings.login_max_failures,
            settings.login_failure_window_seconds,
            settings.login_lock_level_ttl_seconds,
            settings.login_lock_durations_seconds[0],
            settings.login_lock_durations_seconds[1],
            settings.login_lock_durations_seconds[2],
        )
    except RedisError:
        logger.warning(
            "记录登录失败次数失败，继续返回认证错误"
        )


def clear_login_failures(
    scope: str,
) -> None:
    """清理登录失败计数。"""

    failure_key = _failure_key(scope)
    lock_key = _lock_key(scope)
    level_key = _lock_level_key(scope)

    try:
        redis_client.delete(
            failure_key,
            lock_key,
            level_key,
        )
    except RedisError:
        logger.warning(
            "清理登录失败计数失败，继续完成登录"
        )
