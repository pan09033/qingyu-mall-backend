# FastAPI 用户接口练习

当前项目已经实现：

- `GET /`：检查系统是否运行。
- `POST /users/`：创建用户。
- `GET /users/`：查询全部用户。
- 姓名长度和年龄范围的基础校验。

请主要修改：

- `app/routers/users.py`
- `app/schemas/user.py`

不要把所有代码重新放回 `main.py`。

## 第一关：根据编号查询用户

实现：

```text
GET /users/{user_id}
```

要求：

1. `user_id` 必须是大于或等于 `1` 的整数。
2. 找到用户时返回该用户。
3. 找不到时返回状态码 `404`。
4. 错误响应内容为：

```json
{
  "detail": "用户不存在"
}
```

提示：需要使用 `Path`、`HTTPException` 和 `status`。

## 第二关：搜索与分页

扩展现有的：

```text
GET /users/
```

添加三个查询参数：

| 参数 | 默认值 | 规则 |
|---|---:|---|
| `keyword` | `None` | 可选，最大长度20 |
| `skip` | `0` | 大于或等于0 |
| `limit` | `10` | 1到100之间 |

要求：

1. 提供 `keyword` 时，只返回姓名中包含该文字的用户。
2. 使用 `skip` 跳过指定数量的用户。
3. 使用 `limit` 限制最多返回多少名用户。
4. 不提供任何参数时，仍然可以正常查询。

提示：可以使用列表推导式和列表切片。

## 第三关（加分）：部分修改用户

在 `app/schemas/user.py` 中定义：

```python
class UserUpdate(BaseModel):
    ...
```

它的 `name` 和 `age` 都是可选字段，但只要提供就必须通过与创建用户相同的校验。

实现：

```text
PATCH /users/{user_id}
```

要求：

1. 只修改请求体中实际提供的字段。
2. 用户不存在时返回 `404`。
3. 修改成功后返回最新的用户数据。

提示：Pydantic模型可以调用：

```python
user_update.model_dump(exclude_unset=True)
```

## 第四关（加分）：删除用户

实现：

```text
DELETE /users/{user_id}
```

要求：

1. 删除成功时返回状态码 `204`。
2. 用户不存在时返回 `404`。
3. 删除后再次查询该编号，应该得到 `404`。

## 验收顺序

1. 启动项目：`fastapi dev main.py`
2. 打开：`http://127.0.0.1:8000/docs`
3. 创建至少3名用户。
4. 测试存在和不存在的用户编号。
5. 测试姓名搜索。
6. 测试 `skip` 和 `limit`。
7. 测试非法参数，例如 `user_id=0`、`skip=-1`、`limit=101`。

完成第一、二关后，把 `app/routers/users.py` 发来检查。
