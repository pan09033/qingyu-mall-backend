"""Local portfolio preview with fictional data, in-memory SQLite and stub AI.

Run: python -m tests.manual.showcase_preview
Frontend: VITE_API_BASE_URL=http://127.0.0.1:8101
Demo accounts: support_demo / support_admin; password: DemoOnly123!
No real database, Redis, message broker, storage or LLM service is used.
"""

import os
from pathlib import Path
import tempfile
from decimal import Decimal


def build_showcase_app():
    # Import application settings from a temporary empty working directory so
    # the developer's .env is not read. All service credentials are demo-only.
    os.environ.update({
        "DB_USER": "demo", "DB_PASSWORD": "demo-only", "DB_HOST": "127.0.0.1",
        "DB_PORT": "9", "DB_NAME": "demo", "APP_ENV": "testing", "SQL_ECHO": "false",
        "REDIS_HOST": "127.0.0.1", "REDIS_PORT": "9", "REDIS_PASSWORD": "demo-only",
        "RABBITMQ_HOST": "127.0.0.1", "RABBITMQ_PORT": "9", "RABBITMQ_USERNAME": "demo",
        "RABBITMQ_PASSWORD": "demo-only", "JWT_SECRET_KEY": "portfolio-demo-only-not-a-production-key",
        "PAYMENT_CALLBACK_SECRET": "portfolio-demo-only-callback",
        "RAG_DB_HOST": "127.0.0.1", "RAG_DB_PORT": "9", "RAG_DB_PASSWORD": "demo-only",
        "DEEPSEEK_API_KEY": "", "DEEPSEEK_BASE_URL": "http://127.0.0.1:9",
        "RAG_EMBEDDING_MODEL_PATH": "", "MINIO_ENDPOINT": "127.0.0.1:9",
        "MINIO_PUBLIC_BASE_URL": "http://127.0.0.1:9", "MINIO_ACCESS_KEY": "demo",
        "MINIO_SECRET_KEY": "demo-only", "LOG_LEVEL": "WARNING",
    })
    original = Path.cwd()
    project_root = Path(__file__).resolve().parents[2]
    temp_parent = (project_root / "output" / "showcase-tmp").resolve()
    assert temp_parent.is_relative_to(project_root)
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mall-showcase-", dir=temp_parent) as empty_directory:
        try:
            os.chdir(empty_directory)
            from tests.manual.support_preview import build_preview_app
            app = build_preview_app()
        finally:
            os.chdir(original)

    from fastapi.responses import Response
    from sqlalchemy import select
    from app.database import get_db
    from app.models.category import Category
    from app.models.product import Product
    from app.models.user import User

    session_generator = app.dependency_overrides[get_db]()
    db = next(session_generator)
    try:
        for user in db.scalars(select(User)):
            user.name = "商城演示管理员" if user.role == "admin" else "商城演示用户"
        first_category = db.scalar(select(Category))
        first_category.name = "数码配件"
        categories = [first_category, Category(name="桌面办公"), Category(name="日常生活")]
        db.add_all(categories[1:])
        db.flush()
        first = db.scalar(select(Product))
        first.name, first.description = "轻音无线耳机", "演示商品：轻便通勤，日常音乐与语音通话。"
        first.stock = 48
        first.image_url = "http://127.0.0.1:8101/showcase/assets/headphones.svg"
        products = [
            ("简约机械键盘", "keyboard", "169", 32, 1, "演示商品：紧凑布局，适合学习与桌面办公。"),
            ("随行便携音箱", "speaker", "129", 25, 0, "演示商品：便携音箱，满足日常音乐播放需求。"),
            ("暖光阅读台灯", "lamp", "89", 41, 1, "演示商品：可调灯臂，为书桌提供柔和照明。"),
            ("轻量保温杯", "bottle", "49", 60, 2, "演示商品：日常随身饮水，简洁轻便。"),
            ("桌面收纳盒", "box", "39", 52, 2, "演示商品：整理文具与小物件，保持桌面整洁。"),
        ]
        for name, image, price, stock, category_index, description in products:
            db.add(Product(name=name, description=description, price=Decimal(price), stock=stock,
                category_id=categories[category_index].id,
                image_url=f"http://127.0.0.1:8101/showcase/assets/{image}.svg"))
        db.commit()
    finally:
        session_generator.close()

    # Simple original vector drawings are presentation fixtures, not product photos.
    icons = {
        "headphones": '<path d="M104 172v-26a56 56 0 01112 0v26"/><rect x="91" y="154" width="30" height="62" rx="13"/><rect x="199" y="154" width="30" height="62" rx="13"/>',
        "keyboard": '<rect x="65" y="130" width="190" height="85" rx="12"/><path d="M85 151h150M85 174h150M110 195h100M110 140v40M145 140v40M180 140v40M215 140v40"/>',
        "speaker": '<rect x="113" y="95" width="94" height="145" rx="25"/><circle cx="160" cy="177" r="28"/><circle cx="160" cy="128" r="8"/>',
        "lamp": '<path d="M105 235h120M165 230l-32-72 46-52M142 105l44-17 27 43-70 25z"/>',
        "bottle": '<rect x="132" y="83" width="56" height="24" rx="7"/><rect x="123" y="108" width="74" height="138" rx="23"/><path d="M133 152h54"/>',
        "box": '<path d="M82 138l78-28 78 28-78 29zM82 138v83l78 29 78-29v-83M160 167v83M120 182v25"/>',
    }

    @app.get("/showcase/assets/{name}.svg", include_in_schema=False)
    def demo_asset(name: str):
        icon = icons.get(name, icons["box"])
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="280" viewBox="0 0 320 280"><rect width="320" height="280" fill="#eef4f0"/><circle cx="160" cy="158" r="105" fill="#e0eae3"/><g fill="#f7faf8" stroke="#446454" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">{icon}</g></svg>'
        return Response(svg, media_type="image/svg+xml")

    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(build_showcase_app(), host="127.0.0.1", port=8101, log_level="warning")
