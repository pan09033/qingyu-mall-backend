# 本地虚拟机 Docker 部署

此 Compose 项目在同一 Docker 网络运行 MySQL、PostgreSQL/pgvector、Redis、RabbitMQ、MinIO、FastAPI、三个 Worker 和 Vue/Nginx。后端仓库与前端仓库需分别位于 `~/projects/fastApiProject`、`~/projects/mall-frontend`。

## 配置

在后端目录将 `.env.docker.example` 复制为 `.env.docker`，填写独立随机密码、DeepSeek API Key、虚拟机 IP 和本机 BGE 模型路径。`.env.docker` 只保存在虚拟机，权限设置为 `600`。BGE 模型目录必须含 `model.safetensors` 等文件，实际向量维度为 512；Compose 只读挂载模型文件，镜像不包含模型。

`MINIO_PUBLIC_BASE_URL` 是浏览器访问图片的地址，`MINIO_ENDPOINT` 是容器内部访问 MinIO 的地址。商品图片桶仅对 `products/*` 开放匿名读取；上传和删除仍需要后台凭据。

## 首次启动

在后端仓库目录执行：

```bash
docker compose --env-file .env.docker up -d --wait mysql pgvector redis rabbitmq minio
docker compose --env-file .env.docker build backend frontend
docker compose --env-file .env.docker run --rm --no-deps backend python -m alembic upgrade head
docker compose --env-file .env.docker run --rm --no-deps backend python -m alembic -c alembic-rag.ini upgrade head
docker compose --env-file .env.docker up -d --wait backend frontend outbox_worker order_worker rag_worker
```

运行 RAG 迁移前，必须在 PostgreSQL 数据库里启用 `vector` 扩展。全新数据库还需要创建 `product-media` 桶，并仅对 `products/*` 配置匿名 `s3:GetObject`。这些初始化步骤对已建好的虚拟机无需重复。

浏览器访问 `http://192.168.68.22:8088`；后端接口文档在 `http://192.168.68.22:8000/docs`。新数据库没有原本电脑上的商品、用户和图片数据，旧数据需单独迁移或重新录入。

## 日常使用

```bash
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs --tail 100 backend
docker compose --env-file .env.docker stop
docker compose --env-file .env.docker start
```

`stop` 保留容器和数据卷；不要用删除数据卷的命令清理数据库。代码更新后重新构建受影响的镜像，并用 `up -d` 更新对应服务。
