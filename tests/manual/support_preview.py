"""隔离的浏览器验收环境，不读取/写入真实商城数据，也不调用AI。

运行 python -m tests.manual.support_preview。
仅监听127.0.0.1:8101；数据在内存中，退出后消失。
仅测试账户：support_demo / support_admin，密码均为 DemoOnly123!。
前端使用 VITE_API_BASE_URL=http://127.0.0.1:8101 启动。
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def build_preview_app():
    from app.database import Base, get_db
    from app.main import app
    from app.models.category import Category
    from app.models.order import Order
    from app.models.product import Product
    from app.models.user import User
    from app.rag.database import get_rag_db
    from app.rag.services.grounded_qa import no_knowledge_answer
    from app.redis_client import redis_client
    from app.schemas.support import SupportAnswer, SupportSource
    from app.security import hash_password
    from app.services import support

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(name="客服验收用户", age=25, username="support_demo", hashed_password=hash_password("DemoOnly123!"))
        admin = User(name="客服验收管理员", age=25, username="support_admin", role="admin", hashed_password=hash_password("DemoOnly123!"))
        category = Category(name="测试商品")
        db.add_all([user, admin, category])
        db.flush()
        db.add(Product(name="验收耳机", price=Decimal("59"), stock=5, category_id=category.id))
        db.add(Order(user_id=user.id, total_amount=Decimal("59"), status="shipped",
                     expires_at=datetime.now() + timedelta(minutes=30), receiver_name="测试", phone="13800138000",
                     province="广东", city="深圳", district="南山", detail_address="测试地址"))
        db.commit()

    def get_preview_db():
        with Session(engine) as db:
            yield db

    def preview_answer(_db, question, *_args):
        if "地址" in question:
            return SupportAnswer(answer="订单支付后不能继续修改收货地址。[资料1]", kind="knowledge",
                sources=[SupportSource(citation_number=1, source_type="policy", source_id="shipping_policy",
                    title="配送规则 - 修改收货地址", excerpt="订单支付后不能继续修改收货地址。")])
        return no_knowledge_answer()

    app.dependency_overrides[get_db] = get_preview_db
    app.dependency_overrides[get_rag_db] = lambda: Mock()
    support.answer_supported_question = preview_answer
    for name, result in (("get", None), ("set", True), ("incr", 1), ("expire", True), ("eval", 0), ("ttl", -2), ("delete", 0)):
        setattr(redis_client, name, Mock(return_value=result))
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5174"], allow_methods=["*"], allow_headers=["*"])
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(build_preview_app(), host="127.0.0.1", port=8101)
