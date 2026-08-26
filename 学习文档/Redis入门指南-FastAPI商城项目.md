# Redis 入门指南

> 面向当前 FastAPI 商城项目的 Redis 学习笔记  
> 日期：2026-08-25

## 1. Redis 是什么

Redis 是一个以内存为主要存储位置的键值数据库，特点是读写速度快。

常见用途：

- 缓存常用数据
- 保存验证码等临时数据
- 接口限流计数
- 排行榜
- 分布式锁
- 简单消息队列

在当前商城项目中，可以先把 Redis 理解成 MySQL 的辅助工具：

```text
MySQL：保存可靠、长期存在的业务数据
Redis：保存缓存或带过期时间的临时数据
```

Redis 不能简单替代 MySQL。订单、支付、用户和库存等真实业务数据，仍应以 MySQL 为准。

## 2. Redis 与 MySQL 的区别

| 比较项 | MySQL | Redis |
|---|---|---|
| 主要存储位置 | 磁盘 | 内存为主 |
| 访问方式 | SQL 查询 | 根据 Key 访问 |
| 复杂查询 | 支持关联、排序、聚合 | 不擅长复杂关联查询 |
| 适合数据 | 订单、用户、支付、库存 | 缓存、计数、临时状态 |
| 项目角色 | 真实数据来源 | 性能和临时能力补充 |

## 3. Redis 的基本数据结构

### 3.1 String

保存一个字符串、数字或者序列化后的 JSON。

```redis
SET product:detail:1 "机械键盘"
GET product:detail:1
DEL product:detail:1
```

常见场景：

- 商品详情缓存
- 验证码
- 接口访问次数
- 登录失败次数

### 3.2 Hash

保存一个包含多个字段的对象。

```redis
HSET user:1 name "小明" age 18
HGET user:1 name
HGETALL user:1
```

适合保存结构较简单、字段比较稳定的小对象。

### 3.3 List

保存有顺序、允许重复的数据。

```redis
LPUSH tasks "task-1"
RPOP tasks
LRANGE tasks 0 -1
```

常见场景：简单任务队列、最近访问记录。

### 3.4 Set

保存无序、不能重复的数据。

```redis
SADD product:1:tags "键盘" "数码"
SISMEMBER product:1:tags "键盘"
SMEMBERS product:1:tags
```

常见场景：标签、去重集合、用户关注关系。

### 3.5 Sorted Set

每个成员都有一个分数，Redis 根据分数排序。

```redis
ZADD product:sales 100 "product:1"
ZADD product:sales 80 "product:2"
ZRANGE product:sales 0 -1 WITHSCORES
```

常见场景：销量榜、积分榜、热门商品榜。

## 4. Key 的命名

Redis 根据 Key 查找数据，因此 Key 必须含义清晰。

推荐使用冒号分隔：

```text
业务模块:数据用途:资源编号
```

示例：

```text
product:detail:1001
user:profile:42
rate_limit:login:192.168.1.10
```

不同环境可以增加前缀：

```text
dev:mall:product:detail:1001
test:mall:product:detail:1001
prod:mall:product:detail:1001
```

注意：

- 不要使用 `1`、`data`、`cache` 等含义不清的 Key。
- 不要在 Key 中写入密码、Token、手机号等敏感信息。
- Key 不要过长，但要能够看懂含义。

## 5. TTL 过期时间

TTL 是 Time To Live 的缩写，表示 Key 还能存活多长时间。

```redis
SET product:detail:1 "机械键盘" EX 300
TTL product:detail:1
EXPIRE product:detail:1 600
```

上面的 `EX 300` 表示数据在 300 秒后自动过期。

通常需要设置 TTL 的数据：

- 商品缓存
- 验证码
- 登录失败计数
- 接口限流计数
- 临时会话数据

TTL 没有统一答案，需要根据业务允许的数据陈旧程度决定。

## 6. FastAPI 中最重要的缓存模式

当前项目建议先学习 Cache-Aside（旁路缓存）模式。

### 6.1 查询商品详情

```text
收到商品详情请求
        ↓
根据 product_id 组成 Redis Key
        ↓
查询 Redis
   ┌────┴────┐
命中          未命中
 ↓              ↓
直接返回      查询 MySQL
                 ↓
              写入 Redis
                 ↓
              返回商品数据
```

示例代码：

```python
def get_product_detail(product_id: int):
    key = f"product:detail:{product_id}"

    cached = redis_client.get(key)
    if cached is not None:
        return ProductResponse.model_validate_json(cached)

    product = get_product_or_404(db, product_id)
    response = ProductResponse.model_validate(product)

    redis_client.set(
        key,
        response.model_dump_json(),
        ex=300,
    )
    return response
```

## 7. 修改数据后如何处理缓存

假设 MySQL 中的商品价格已经修改，但 Redis 仍保存旧价格，用户就会看到旧数据。

当前阶段使用下面的策略：

```text
修改数据库对象
    ↓
db.commit() 成功
    ↓
删除对应 Redis 缓存
```

示例：

```python
product.price = product_data.price
db.commit()

redis_client.delete(
    f"product:detail:{product.id}"
)
```

为什么删除缓存，而不是直接修改缓存？

- 删除逻辑更简单。
- 下一次查询会从 MySQL 获取最新数据。
- 重新查询后会自动生成新的缓存。

必须先确保 `db.commit()` 成功，再处理缓存。如果数据库提交失败，应当执行 `rollback()`，不能继续删除或更新缓存。

## 8. 当前商城项目中的 Redis 功能

建议按照下面的顺序学习：

| 顺序 | 功能 | Redis 结构 | 学习重点 |
|---|---|---|---|
| 1 | 商品详情缓存 | String + JSON | 命中、未命中、TTL、缓存失效 |
| 2 | 登录接口限流 | String 计数器 | `INCR`、`EXPIRE`、HTTP 429 |
| 3 | 验证码 | String + 短 TTL | 过期、一次性使用 |
| 4 | 商品排行榜 | Sorted Set | 分数、排名、范围查询 |
| 5 | 分布式锁 | `SET NX EX` | 原子性、锁标识、正确释放 |

第一阶段只需要完成商品详情缓存和登录限流，不需要一次学习全部功能。

## 9. 常见缓存问题

### 9.1 缓存穿透

大量请求查询根本不存在的商品，Redis 中没有数据，每次请求都访问 MySQL。

常见处理：

- 校验请求参数。
- 对不存在的数据设置很短的空值缓存。
- 对恶意请求进行限流。

### 9.2 缓存击穿

某个热门商品的缓存刚好过期，大量请求同时查询 MySQL。

后续可以使用互斥锁、逻辑过期或者热点数据预热。初学阶段先理解现象即可。

### 9.3 缓存雪崩

大量 Key 在同一时间过期，数据库突然收到大量请求。

常见处理：给 TTL 增加一个小范围随机值，避免大量缓存同时过期。

### 9.4 Redis 无法连接

商品缓存属于辅助功能。Redis 暂时不可用时，商品查询应该尽量回退到 MySQL，不能让整个商城一起失效。

需要配置：

- Redis 连接超时
- 异常日志
- 必要的降级逻辑

## 10. 必须记住的安全规则

- 不要缓存明文密码、密码哈希、密钥和不必要的完整 Token。
- 生产环境不要使用 `KEYS *` 扫描全部数据，应该使用 `SCAN`。
- 不要让单个 Key 保存无限增长的数据。
- Redis 应设置访问密码和网络访问限制。
- 不要把 Redis 端口直接暴露到公网。
- 缓存不能代替后端权限校验。

## 11. 学习路线

1. 运行 Redis，进入 `redis-cli`。
2. 练习 `SET`、`GET`、`DEL`、`EXPIRE`、`TTL`。
3. 理解 String、Hash、List、Set、Sorted Set。
4. 在 Python 中连接 Redis。
5. 为 `GET /products/{product_id}` 添加缓存。
6. 修改或删除商品后，让缓存失效。
7. 为登录接口增加限流并返回 HTTP 429。
8. 编写自动化测试验证缓存命中、失效和异常回退。

## 12. Redis 入门完成标准

达到下面这些要求，就可以认为 Redis 基础入门已经完成：

- 能解释 Redis 和 MySQL 的职责区别。
- 能根据业务设计清晰的 Key。
- 知道哪些数据需要 TTL。
- 能说明 Cache-Aside 的查询流程。
- 知道数据库更新后为什么要让缓存失效。
- 能解释缓存穿透、击穿和雪崩。
- 能使用测试验证缓存是否生效。

## 13. 复习自测

1. Redis 为什么不能直接替代商城项目中的 MySQL？
2. TTL 的作用是什么？哪些数据通常需要 TTL？
3. 商品详情缓存未命中时，程序应该按照什么顺序执行？
4. 修改商品后，为什么要在 `db.commit()` 成功后再删除缓存？
5. `product:detail:1001` 的三个部分分别代表什么？

### 参考答案

1. MySQL 负责可靠业务数据、事务和复杂查询，Redis 在本项目中主要负责缓存和临时状态。
2. TTL 控制 Key 的存活时间。缓存、验证码和限流计数等临时数据通常需要 TTL。
3. 先查询 Redis；未命中时查询 MySQL；把结果写入 Redis并设置 TTL；最后返回结果。
4. 只有数据库提交成功，最新数据才真正生效；否则处理缓存可能造成错误状态。
5. `product` 表示业务模块，`detail` 表示数据用途，`1001` 表示商品编号。

---

下一步：先在虚拟机中运行 Redis 并练习基本命令，然后把商品详情缓存接入当前 FastAPI 商城项目。
