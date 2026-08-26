# FastAPI 学习复习笔记

## 一、当前阶段的学习目标

今天的学习内容围绕一个“用户管理系统”展开，目标是掌握：

1. Python 类型注解。
2. Python 装饰器的基本原理。
3. HTTP、REST 和 JSON。
4. 创建并启动 FastAPI 项目。
5. 使用 Pydantic 接收和校验请求体。
6. 使用 `APIRouter` 拆分多文件项目。
7. 使用路径参数和查询参数。
8. 使用 `HTTPException` 返回业务错误。
9. 使用 `/docs` 测试接口。

---

## 二、Python 类型注解

### 1. 变量类型

```python
name: str = "小明"
age: int = 18
price: float = 99.9
active: bool = True
```

### 2. 容器类型

```python
names: list[str] = ["小明", "小红"]
scores: dict[str, int] = {
    "小明": 90,
    "小红": 95,
}
```

### 3. 函数参数和返回值

```python
def add(a: int, b: int) -> int:
    return a + b
```

- `a: int`：参数 `a` 预期是整数。
- `b: int`：参数 `b` 预期是整数。
- `-> int`：函数预期返回整数。

没有返回值时：

```python
def show_message(message: str) -> None:
    print(message)
```

### 4. 可选类型

```python
keyword: str | None = None
```

表示 `keyword` 可以是字符串，也可以是 `None`。

普通 Python 不会仅凭类型注解强制限制数据，但 FastAPI 和 Pydantic 会读取类型注解并用于数据转换、校验和文档生成。

---

## 三、`Annotated` 的作用

导入：

```python
from typing import Annotated
```

基本格式：

```python
Annotated[原始类型, 附加信息]
```

路径参数示例：

```python
user_id: Annotated[int, Path(ge=1)]
```

含义：

- `user_id` 是整数。
- `user_id` 来自 URL 路径。
- `user_id` 必须大于或等于 1。

查询参数示例：

```python
keyword: Annotated[
    str | None,
    Query(max_length=20),
] = None
```

含义：

- `keyword` 可以是字符串或 `None`。
- 它是查询参数。
- 字符串最大长度是 20。
- 没有提供时，默认值是 `None`。

常见校验参数：

| 参数 | 含义 |
|---|---|
| `gt` | 大于 |
| `ge` | 大于或等于 |
| `lt` | 小于 |
| `le` | 小于或等于 |
| `min_length` | 最小长度 |
| `max_length` | 最大长度 |

---

## 四、装饰器基础

### 1. 普通装饰器

```python
@my_decorator
def study():
    print("正在学习")
```

可以近似理解为：

```python
study = my_decorator(study)
```

装饰器可以在不直接修改原函数代码的情况下，对函数进行包装、登记或扩展。

### 2. FastAPI 路由装饰器

```python
@app.get("/")
def root():
    return {"message": "运行成功"}
```

表示：

```text
收到 GET / 请求时，调用 root() 函数
```

类似的装饰器还有：

```python
@app.post()
@app.put()
@app.patch()
@app.delete()
```

拆分路由后使用：

```python
@router.get()
@router.post()
```

---

## 五、HTTP、REST 和 JSON

### 1. 请求和响应

```text
客户端发送请求
      ↓
FastAPI 处理请求
      ↓
服务器返回响应
```

### 2. 常见 HTTP 方法

| 方法 | 常见用途 |
|---|---|
| `GET` | 查询数据 |
| `POST` | 创建数据 |
| `PUT` | 完整修改数据 |
| `PATCH` | 部分修改数据 |
| `DELETE` | 删除数据 |

### 3. 常见状态码

| 状态码 | 含义 |
|---:|---|
| `200` | 请求成功 |
| `201` | 创建成功 |
| `204` | 成功但没有响应体 |
| `400` | 请求有问题 |
| `401` | 未认证 |
| `403` | 没有权限 |
| `404` | 资源不存在 |
| `422` | 参数或请求体校验失败 |
| `500` | 服务器内部错误 |

### 4. REST 风格

```text
POST   /users/           创建用户
GET    /users/           查询用户列表
GET    /users/{user_id}  查询一个用户
PATCH  /users/{user_id}  部分修改用户
DELETE /users/{user_id}  删除用户
```

URL 主要表达“操作哪个资源”，HTTP 方法表达“执行什么操作”。

### 5. JSON 和 Python 类型

| JSON | Python |
|---|---|
| object | `dict` |
| array | `list` |
| string | `str` |
| number | `int` 或 `float` |
| boolean | `bool` |
| `null` | `None` |

JSON 使用：

```json
{
  "name": "小明",
  "age": 18,
  "active": true
}
```

注意 JSON 使用双引号，布尔值写作 `true` 和 `false`。

---

## 六、当前项目结构

```text
fastApiProject/
├── requirements.txt
├── PRACTICE.md
├── tests/manual/api.http
└── app/
    ├── __init__.py
    ├── main.py
    ├── store.py
    ├── routers/
    │   ├── __init__.py
    │   └── users.py
    └── schemas/
        ├── __init__.py
        └── user.py
```

各文件职责：

| 文件 | 职责 |
|---|---|
| `app/main.py` | 创建 FastAPI 应用并注册路由 |
| `app/routers/users.py` | 用户相关 HTTP 接口 |
| `app/schemas/user.py` | 用户请求和响应数据模型 |
| `app/store.py` | 临时内存数据 |
| `__init__.py` | 标识并初始化 Python 包 |
| `requirements.txt` | 记录项目依赖 |
| `tests/manual/api.http` | 保存手工接口测试请求 |

`__init__.py` 与类中的 `__init__()` 不同：

- `def __init__()`：初始化对象。
- `__init__.py`：初始化并标识 Python 包。

---

## 七、创建 FastAPI 主应用

`app/main.py`：

```python
from fastapi import FastAPI

from app.routers import users


app = FastAPI(title="用户管理系统")

app.include_router(users.router)


@app.get("/", tags=["系统"])
def root() -> dict[str, str]:
    return {
        "message": "用户管理系统运行成功"
    }
```

关键代码：

```python
app = FastAPI(...)
```

这里的 `FastAPI` 是类，`app` 是对象。

```python
app.include_router(users.router)
```

表示把用户路由中的接口加入主应用。

---

## 八、`APIRouter` 的作用

```python
router = APIRouter(
    prefix="/users",
    tags=["用户管理"],
)
```

### `prefix`

```python
prefix="/users"
```

表示这个路由中的所有地址都以 `/users` 开头。

例如：

```python
@router.get("/")
```

最终地址是：

```text
GET /users/
```

```python
@router.get("/{user_id}")
```

最终地址是：

```text
GET /users/{user_id}
```

### `tags`

```python
tags=["用户管理"]
```

用于在 `/docs` 中对接口进行分组，不会改变请求路径。

---

## 九、Pydantic 请求体校验

`app/schemas/user.py`：

```python
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=20,
        description="用户姓名",
    )
    age: int = Field(
        ge=6,
        le=100,
        description="用户年龄",
    )
```

请求：

```json
{
  "name": "小明",
  "age": 18
}
```

FastAPI 会：

1. 读取 JSON 请求体。
2. 根据 `UserCreate` 转换并校验数据。
3. 校验成功后创建 `UserCreate` 对象。
4. 把对象传入接口函数。

因此可以通过属性读取：

```python
user.name
user.age
```

年龄不在 6 到 100 之间时，FastAPI 会自动返回 422。

---

## 十、三种参数的区别

### 1. 路径参数

```python
@router.get("/{user_id}")
def get_user(user_id: int):
    ...
```

请求：

```text
GET /users/10
```

`10` 是路径参数，通常用于确定一个具体资源。

### 2. 查询参数

```python
@router.get("/")
def get_users(
    keyword: str | None = None,
    skip: int = 0,
    limit: int = 10,
):
    ...
```

请求：

```text
GET /users/?keyword=小&skip=0&limit=10
```

查询参数通常用于搜索、筛选、排序和分页。

### 3. 请求体

```python
@router.post("/")
def create_user(user: UserCreate):
    ...
```

客户端通过 JSON 发送请求体：

```json
{
  "name": "小明",
  "age": 18
}
```

---

## 十一、用户路由建议版本

下面代码是当前两关练习的建议整理版本：

```python
from typing import Annotated

from fastapi import (
    APIRouter,
    HTTPException,
    Path,
    Query,
    status,
)

from app.schemas.user import UserCreate
from app.store import users


router = APIRouter(
    prefix="/users",
    tags=["用户管理"],
)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user: UserCreate,
) -> dict[str, int | str]:
    new_user: dict[str, int | str] = {
        "id": len(users) + 1,
        "name": user.name,
        "age": user.age,
    }

    users.append(new_user)
    return new_user


@router.get("/")
def get_users(
    keyword: Annotated[
        str | None,
        Query(min_length=1, max_length=20),
    ] = None,
    skip: Annotated[
        int,
        Query(ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 10,
) -> list[dict[str, int | str]]:
    filtered_users = users

    if keyword is not None:
        filtered_users = [
            user
            for user in users
            if keyword in str(user["name"])
        ]

    return filtered_users[skip:skip + limit]


@router.get("/{user_id}")
def get_user(
    user_id: Annotated[
        int,
        Path(ge=1),
    ],
) -> dict[str, int | str]:
    for user in users:
        if user["id"] == user_id:
            return user

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="用户不存在",
    )
```

推荐排列顺序：

```text
POST /users/            创建用户
GET  /users/            查询、搜索和分页
GET  /users/{user_id}   查询单个用户
```

---

## 十二、筛选和分页原理

### 1. 关键词筛选

```python
filtered_users = [
    user
    for user in users
    if keyword in str(user["name"])
]
```

含义：

```text
遍历 users
    ↓
检查 keyword 是否包含在用户姓名中
    ↓
符合条件的用户加入新列表
```

### 2. 列表切片分页

```python
return filtered_users[skip:skip + limit]
```

假设：

```python
skip = 2
limit = 3
```

实际切片：

```python
filtered_users[2:5]
```

表示跳过前两条，最多返回三条。

---

## 十三、业务错误与参数错误

### 1. 资源不存在：404

```python
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="用户不存在",
)
```

响应：

```json
{
  "detail": "用户不存在"
}
```

异常应当写在循环结束后：

```python
for user in users:
    if user["id"] == user_id:
        return user

raise HTTPException(...)
```

不能在第一次不匹配时立即抛出异常，否则不会继续检查后面的用户。

### 2. 校验失败：422

下面情况应该由 FastAPI 自动返回 422：

```text
/users/abc
/users/0
/users/?skip=-1
/users/?limit=0
/users/?limit=101
```

### 3. 404 和 422 的区别

- 422：输入的格式或范围不符合接口规则。
- 404：输入本身合法，但对应数据不存在。

---

## 十四、自动接口文档

启动服务器后访问：

```text
http://127.0.0.1:8000/docs
```

`/docs` 是 FastAPI 自动生成的 Swagger UI，可以：

- 查看所有接口。
- 查看路径参数、查询参数和请求体。
- 查看数据校验规则。
- 点击 `Try it out` 和 `Execute` 发送请求。
- 查看响应状态码和响应体。

其他自动地址：

```text
/redoc          另一种文档页面
/openapi.json   原始 OpenAPI 描述
```

---

## 十五、启动项目

当前根目录的 `main.py` 已删除，因此应从项目根目录启动：

```powershell
cd D:\pythonstudy\fastApiProject
C:\Users\acerpbd\miniconda3\python.exe -m fastapi dev app/main.py
```

PyCharm 中的 FastAPI 运行配置也应指向：

```text
D:\pythonstudy\fastApiProject\app\main.py
```

工作目录应当是：

```text
D:\pythonstudy\fastApiProject
```

今天遇到过两个启动问题：

1. 根目录 `main.py` 已删除，但运行配置仍指向旧文件。
2. 系统 Python 没有安装 FastAPI，而 PyCharm 使用的是 Miniconda Python。

当出现“明明安装过包但提示找不到”时，优先检查终端和 PyCharm 是否使用同一个 Python 解释器。

---

## 十六、今天代码中发现的问题

### 1. 函数名称写反

查询一个用户应该使用单数：

```python
def get_user(...):
```

查询用户列表应该使用复数：

```python
def get_users(...):
```

函数名不会改变 URL，但正确命名能让代码更容易理解。

### 2. `keyword` 类型应包含 `None`

不推荐：

```python
keyword: Annotated[str, Query(...)] = None
```

推荐：

```python
keyword: Annotated[str | None, Query(...)] = None
```

因为默认值是 `None`，类型注解也应该明确允许 `None`。

### 3. `keyword` 缺少最大长度

练习要求最大长度为 20：

```python
Query(min_length=1, max_length=20)
```

### 4. `limit` 不应该允许为 0

当前错误规则：

```python
Query(ge=0, le=100)
```

正确规则：

```python
Query(ge=1, le=100)
```

实际测试中，当前代码对 `limit=0` 返回了 200 和空列表，但练习要求它返回 422。

### 5. 删除未使用的导入

如果没有使用：

```python
Dict
List
```

就不需要导入。Python 3.10+ 可以直接使用：

```python
dict[str, int]
list[str]
```

### 6. 导入应集中整理

推荐：

```python
from typing import Annotated

from fastapi import (
    APIRouter,
    HTTPException,
    Path,
    Query,
    status,
)
```

不要把同一个库拆成多个相隔很远的导入区块。

---

## 十七、当前内存存储的限制

```python
users: list[dict[str, int | str]] = []
```

这只是学习阶段的临时存储：

- 服务器重启后数据会清空。
- 多进程运行时不能可靠共享。
- 不适合真实生产项目。
- 删除用户后，使用 `len(users) + 1` 可能产生重复编号。

后续学习数据库后，会把它替换为 SQLite 或 PostgreSQL。

---

## 十八、复习自测

尝试不用看答案回答：

1. `app` 和 `router` 分别是什么对象？
2. `prefix="/users"` 有什么作用？
3. `tags=["用户管理"]` 会不会改变 URL？
4. `app.include_router(users.router)` 有什么作用？
5. 路径参数、查询参数和请求体有什么区别？
6. `Annotated[int, Path(ge=1)]` 每一部分是什么意思？
7. 为什么 `keyword` 的类型应该是 `str | None`？
8. 404 和 422 有什么区别？
9. 为什么 `raise HTTPException` 应该放在循环外？
10. `/docs` 页面是如何根据代码自动生成的？
11. `skip` 和 `limit` 怎样通过列表切片实现分页？
12. 为什么真实项目不能长期使用内存列表保存数据？

### 参考答案

建议先独立回答，再展开下面的答案进行核对。

<details>
<summary>点击展开参考答案</summary>

#### 1. `app` 和 `router` 分别是什么对象？

```python
app = FastAPI()
router = APIRouter()
```

- `app` 是 `FastAPI` 类的实例，代表完整的 Web 应用。
- `router` 是 `APIRouter` 类的实例，代表一组可以独立组织的路由。
- `router` 可以先登记用户、商品等某一类接口，再通过 `app.include_router()` 加入主应用。

#### 2. `prefix="/users"` 有什么作用？

它为当前 `router` 中的所有路由统一添加 `/users` 路径前缀。

例如：

```python
router = APIRouter(prefix="/users")


@router.get("/")
def get_users():
    ...
```

最终路径是：

```text
GET /users/
```

下面的路由：

```python
@router.get("/{user_id}")
```

最终路径是：

```text
GET /users/{user_id}
```

#### 3. `tags=["用户管理"]` 会不会改变 URL？

不会。

`tags` 只负责在 `/docs` 中对接口进行分类展示，不会改变 URL、请求方法或业务逻辑。

#### 4. `app.include_router(users.router)` 有什么作用？

它把 `users.router` 中登记的所有路由添加到主 `FastAPI` 应用中。

如果没有执行：

```python
app.include_router(users.router)
```

那么用户路由虽然已经写在 `users.py` 中，但主应用无法访问这些接口，它们也不会出现在 `/docs` 中。

#### 5. 路径参数、查询参数和请求体有什么区别？

路径参数是 URL 路径的一部分，通常用于确定一个具体资源：

```text
GET /users/10
```

其中 `10` 是 `user_id` 路径参数。

查询参数位于 `?` 后面，通常用于搜索、筛选和分页：

```text
GET /users/?keyword=小&skip=0&limit=10
```

请求体通常是客户端发送的 JSON 数据，常用于创建或修改资源：

```json
{
  "name": "小明",
  "age": 18
}
```

#### 6. `Annotated[int, Path(ge=1)]` 每一部分是什么意思？

```python
Annotated[int, Path(ge=1)]
```

- `Annotated`：在原始类型上附加额外信息。
- `int`：参数应当是整数。
- `Path(...)`：告诉 FastAPI 这是路径参数，并提供额外校验规则。
- `ge=1`：数值必须大于或等于 1。

如果客户端传入 `abc` 或 `0`，FastAPI 会在调用接口函数前返回 422。

#### 7. 为什么 `keyword` 的类型应该是 `str | None`？

因为它的默认值是 `None`，表示客户端可以不提供 `keyword`。类型注解也应该与实际取值保持一致：

```python
keyword: str | None = None
```

其中：

- 提供参数时，值是 `str`。
- 不提供参数时，值是 `None`。

#### 8. 404 和 422 有什么区别？

`404 Not Found` 表示请求格式正确，但对应资源不存在。

例如：

```text
GET /users/999
```

`999` 是合法整数，但系统中没有这个用户。

`422 Unprocessable Content` 表示参数或请求体没有通过校验，接口函数通常还没有开始执行业务逻辑。

例如：

```text
GET /users/abc
GET /users/0
GET /users/?limit=0
```

#### 9. 为什么 `raise HTTPException` 应该放在循环外？

需要先检查列表中的所有用户：

```python
for user in users:
    if user["id"] == user_id:
        return user

raise HTTPException(...)
```

如果把异常放在循环内部的 `else` 中，第一个用户编号不匹配时就会立即返回 404，后面的用户将没有机会被检查。

#### 10. `/docs` 页面是如何根据代码自动生成的？

FastAPI会读取：

- 路由装饰器，例如 `@router.get()`。
- 路径和查询参数。
- Python类型注解。
- Pydantic模型。
- 状态码和接口说明。

FastAPI根据这些信息生成 OpenAPI 描述：

```text
/openapi.json
```

Swagger UI 再读取这份 OpenAPI 数据，生成可交互的：

```text
/docs
```

#### 11. `skip` 和 `limit` 怎样通过列表切片实现分页？

使用：

```python
filtered_users[skip:skip + limit]
```

例如：

```python
skip = 2
limit = 3
```

切片就是：

```python
filtered_users[2:5]
```

含义是跳过前两条数据，最多返回接下来的三条数据。

#### 12. 为什么真实项目不能长期使用内存列表保存数据？

内存列表存在以下限制：

- 服务器重启后数据会全部消失。
- 多个服务器进程之间不能可靠共享数据。
- 缺少数据库事务和并发控制。
- 不方便进行复杂查询、排序和统计。
- 缺少唯一约束、外键和索引。
- 删除数据后，使用 `len(users) + 1` 生成编号可能造成重复 ID。

真实项目通常使用 SQLite、PostgreSQL、MySQL 等数据库持久化数据。

</details>

---

## 十九、下一步学习路线

建议继续按照以下顺序：

1. `PATCH /users/{user_id}`：部分修改用户。
2. `DELETE /users/{user_id}`：删除用户。
3. Pydantic 响应模型。
4. 自定义 Pydantic 字段校验器。
5. FastAPI 依赖注入 `Depends`。
6. SQL 基础。
7. SQLAlchemy 与数据库持久化。
8. 用户登录、密码哈希和 JWT。
9. 接口自动化测试。
