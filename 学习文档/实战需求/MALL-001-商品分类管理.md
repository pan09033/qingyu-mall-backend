# MALL-001：商品分类管理

## 1. 需求背景

当前商品没有分类，用户无法按照“电脑配件”“办公用品”等类别浏览商品。
商城需要先建立独立的商品分类资源，下一张需求再将商品与分类关联。

## 2. 用户故事

- 作为顾客，我希望查看商品分类，以便后续按照分类浏览商品。
- 作为管理员，我希望创建、修改和删除分类，以便维护商城目录。

## 3. 数据模型

新增 `categories` 表：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | 整数 | 主键、自增 | 分类编号 |
| `name` | `VARCHAR(30)` | 非空、唯一 | 分类名称 |
| `description` | `VARCHAR(200)` | 可以为空 | 分类说明 |

本需求暂时不修改 `products` 表。

## 4. API 契约

### 4.1 查询分类列表

```http
GET /categories/?skip=0&limit=10
```

公开接口，不要求登录。

成功：`200 OK`

```json
{
  "items": [
    {
      "id": 1,
      "name": "电脑配件",
      "description": "键盘、鼠标和显示器"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 10
}
```

### 4.2 查询单个分类

```http
GET /categories/{category_id}
```

公开接口。分类不存在时返回 `404`。

### 4.3 创建分类

```http
POST /categories/
Authorization: Bearer <admin_token>
Content-Type: application/json
```

请求体：

```json
{
  "name": "电脑配件",
  "description": "键盘、鼠标和显示器"
}
```

成功：`201 Created`

### 4.4 修改分类

```http
PATCH /categories/{category_id}
Authorization: Bearer <admin_token>
Content-Type: application/json
```

请求体字段可以省略，但至少应提供一个字段：

```json
{
  "description": "电脑周边设备"
}
```

成功：`200 OK`。

### 4.5 删除分类

```http
DELETE /categories/{category_id}
Authorization: Bearer <admin_token>
```

成功：`204 No Content`。

## 5. 数据校验规则

1. `name` 长度为 1～30，保存前去除两侧空格。
2. `name` 不能是纯空格。
3. 分类名称不能重复。
4. `description` 可以省略或为 `null`，最大长度为 200。
5. `skip` 必须大于或等于 0。
6. `limit` 必须为 1～100。
7. `category_id` 必须大于或等于 1。

## 6. 权限规则

| 接口 | 未登录 | 普通用户 | 管理员 |
|---|---:|---:|---:|
| 查询列表、查询单个分类 | 允许 | 允许 | 允许 |
| 创建、修改、删除分类 | 401 | 403 | 允许 |

## 7. 错误响应

| 场景 | 状态码 | `detail` |
|---|---:|---|
| 分类不存在 | 404 | `商品分类不存在` |
| 分类名称重复 | 409 | `商品分类名称已存在` |
| 未登录 | 401 | 认证错误信息 |
| 普通用户执行管理操作 | 403 | `需要管理员权限` |
| 请求参数校验失败 | 422 | Pydantic 校验信息 |
| 数据库操作失败 | 500 | 对应的分类操作失败信息 |

## 8. 分层要求

```text
Model       categories 表映射
Schema      创建、修改、响应和列表模型
Repository  分类的基础查询和写入操作
Service     唯一性检查、异常和事务
Router      HTTP 参数、权限和响应
Migration   创建 categories 表
Tests       权限和核心业务验收
```

Router 不应直接堆放全部数据库业务逻辑。

## 9. 验收标准

- [ ] `categories` ORM 模型完成。
- [ ] Pydantic 创建、修改、响应和列表模型完成。
- [ ] Repository、Service、Router 分层完成。
- [ ] Alembic 能创建和删除 `categories` 表。
- [ ] 分类名称存在数据库唯一约束。
- [ ] 公开查询接口正常。
- [ ] 管理员可以创建、修改和删除分类。
- [ ] 普通用户不能执行分类管理操作。
- [ ] 重复名称返回 409。
- [ ] 不存在的分类返回 404。
- [ ] 自动化测试全部通过。
- [ ] `alembic check` 不存在待迁移变更。

## 10. 本次不做的内容

- 商品与分类的外键关系。
- 多级分类和父子分类。
- 分类图片。
- 分类排序。
- 分类软删除。

## 11. 开发前分析题

开始编码前，请回答：

1. 需要新建哪些 Python 文件？
2. 哪两个查询接口应当公开？
3. 哪三个接口需要 `get_current_admin`？
4. 分类名称重复为什么使用 409，而不是 404？
5. 本需求为什么需要 Alembic 迁移？
6. 你准备先实现 Model、Schema、Service、Router 中的哪一层？为什么？

