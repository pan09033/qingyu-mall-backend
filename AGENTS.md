# Repository Guidelines

## Project Structure & Architecture

Application code lives in `app/`. Keep HTTP handling in `routers/`, validation models in `schemas/`, business rules in `services/`, database access in `repositories/`, and SQLAlchemy mappings in `models/`. RabbitMQ integration belongs in `app/mq/`. Alembic revisions live in `migrations/`; automated tests live in `tests/`; `practice/`, `docs/`, and `学习文档/` contain learning material rather than production code.

Preserve the existing flow: Router → Schema → Service → Repository → Model/MySQL. Keep RAG APIs, schemas, services, ingestion, providers, and vector-store access separated. A RAG failure must not disrupt product, order, or payment endpoints.

## Build, Test, and Development Commands

Run commands from `D:\pythonstudy\fastApiProject` in the `qingyu-mall` Conda environment:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
python -m pytest -q
python -m pytest tests/test_products.py -q
python -m alembic upgrade head
```

The first command installs dependencies, the second starts the API, the next two run all or focused tests, and the last applies migrations.

## Coding Style & Naming Conventions

Use four-space indentation and type hints for public functions and service boundaries. Name modules, functions, and variables with `snake_case`; classes with `PascalCase`; constants with `UPPER_CASE`. Keep routers thin and follow the surrounding import and formatting style. No formatter or linter is currently enforced by repository configuration.

## Testing Guidelines

Use pytest. Name files `test_<area>.py` and tests `test_<expected_behavior>`. Existing fixtures use in-memory SQLite and mock Redis. Mock PostgreSQL vector access, AI providers, RabbitMQ, and MinIO in ordinary unit tests; do not require live services or credentials. Cover success, permission, validation, and dependency-failure paths, then run the full suite before a pull request.

## Commits, Pull Requests, and Security

Use concise imperative commits such as `Add document retrieval service`. Keep each commit focused. Pull requests should explain the problem, resulting behavior, migrations or configuration changes, and test results; link an issue when one exists.

Store secrets only in `.env`. Put placeholders in `.env.example`, set timeouts for external services, and never commit credentials or destructive data-reset scripts. Preserve unrelated uncommitted learning files.
