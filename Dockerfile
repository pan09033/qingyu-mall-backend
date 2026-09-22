# 与本地 qingyu-mall 环境保持相同的 Python 主次版本。
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 先安装依赖，使业务代码变化时可以复用这一层。
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        'torch==2.9.1+cpu' \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check

# 规则文档供 RAG 索引使用；迁移和脚本供后续独立任务复用。
COPY app/ ./app/
COPY knowledge/ ./knowledge/
COPY migrations/ ./migrations/
COPY rag_migrations/ ./rag_migrations/
COPY scripts/ ./scripts/
COPY alembic.ini alembic-rag.ini ./

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
