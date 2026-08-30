from getpass import getpass

import redis


redis_password = getpass("请输入 Redis 密码：")

redis_client = redis.Redis(
    host="127.0.0.1",
    port=6379,
    password=redis_password,
    protocol=2,
    decode_responses=True,
)

# 请你补写：调用 redis_client 的 ping 方法
result = redis_client.ping()

print("Redis 连接结果：", result)

save_result = redis_client.set("my_key", "Hello, Redis!")
print("保存结果：", save_result)

save_value = redis_client.get("my_key")
print("获取的值：", save_value)

login_fail_key = "practice:login_fail:ttl_demo"
fail_count = redis_client.incr(login_fail_key)

if fail_count == 1:
    redis_client.expire(
        login_fail_key,
        60,
    )

remaining_ttl = redis_client.ttl(
    login_fail_key
)

print("登录失败次数：", fail_count)
print("剩余过期时间：", remaining_ttl, "秒")
