# FastAPI 用户、商品与订单管理项目

这是一个用于学习 FastAPI、SQLAlchemy、Alembic、JWT 和 RBAC 的项目。

## 目录结构

```text
fastApiProject/
├── app/               # 正式应用代码
│   ├── models/        # SQLAlchemy 数据库模型
│   ├── repositories/  # 数据访问层
│   ├── routers/       # API 路由层
│   ├── schemas/       # Pydantic 请求与响应模型
│   └── services/      # 业务逻辑层
├── migrations/        # Alembic 数据库迁移
├── tests/             # pytest 自动化测试和手工请求
├── practice/          # 早期数据库练习代码
├── 学习文档/           # 每日总结与复习资料
├── .env               # 本机配置，不提交到 Git
├── alembic.ini        # Alembic 配置
└── requirements.txt   # Python 依赖
```

## 安装与配置

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env`，为数据库、Redis、JWT 和支付回调设置真实配置。生产环境会拒绝短密钥、共用密钥、SQL 日志和通配符 CORS。

## 数据库迁移

```powershell
python -m alembic current
python -m alembic upgrade head
```

迁移链兼容早期已经手工创建 `products` 表并 stamp 基线的数据库，也支持新建空数据库。

## 启动项目

```powershell
python -m uvicorn app.main:app --reload
```

Swagger 文档：`http://127.0.0.1:8000/docs`

## 自动化测试

```powershell
python -m pytest -v
```

测试使用内存 SQLite，不会修改开发 MySQL 数据。
