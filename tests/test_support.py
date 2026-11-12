from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.main import app
from app.models.order import Order
from app.models.refund_request import RefundRequest
from app.models.support import SupportTurn
from app.models.user import User
from app.rag.database import get_rag_db
from app.rag.exceptions import RagServiceUnavailableError
from app.schemas.support import SupportAnswer


@pytest.fixture(autouse=True)
def isolated_ai(client):
    app.dependency_overrides[get_rag_db] = lambda: Mock()
    with patch("app.routers.support.get_embedding_provider") as embedding, patch("app.routers.support.get_chat_provider") as chat:
        embedding.side_effect = AssertionError("测试不应加载真实模型")
        chat.side_effect = AssertionError("测试不应调用真实API")
        yield
    app.dependency_overrides.pop(get_rag_db, None)


def create_conversation(client, headers):
    response = client.post("/support/conversations", headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def ask(client, headers, conversation_id, question, request_id=None):
    return client.post(f"/support/conversations/{conversation_id}/messages", headers=headers,
                       json={"question": question, "request_id": request_id or str(uuid4())})


def add_order(db, user_id, status="paid"):
    order = Order(user_id=user_id, total_amount=Decimal("99.00"), status=status,
                  expires_at=datetime.now() + timedelta(minutes=30), receiver_name="隐私收件人",
                  phone="13800138000", province="广东", city="深圳", district="南山", detail_address="隐私地址")
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def current_user(db):
    return db.scalar(select(User).where(User.username == "current_user"))


def test_requires_login_and_does_not_accept_client_identity(client, auth_headers):
    assert client.get("/support/conversations").status_code == 401
    conversation_id = create_conversation(client, auth_headers)
    response = client.post(f"/support/conversations/{conversation_id}/messages", headers=auth_headers,
                          json={"question": "查询订单", "request_id": str(uuid4()), "user_id": 999})
    assert response.status_code == 422
    assert ask(client, auth_headers, conversation_id, "   ").status_code == 422


def test_owned_order_followup_and_fresh_status(client, auth_headers, db_session):
    order = add_order(db_session, current_user(db_session).id)
    conversation_id = create_conversation(client, auth_headers)
    first = ask(client, auth_headers, conversation_id, f"订单{order.id}发货了吗？")
    assert first.status_code == 200
    assert first.json()["response"]["order"]["status"] == "paid"
    assert "隐私" not in first.text and "13800138000" not in first.text
    order.status = "shipped"
    db_session.commit()
    followup = ask(client, auth_headers, conversation_id, "那这一单还能退吗？").json()["response"]
    assert followup["order"]["status"] == "shipped"
    assert "退货退款" in followup["answer"]
    assert "没有代你提交退款" in followup["answer"]
    detail = client.get(f"/support/conversations/{conversation_id}", headers=auth_headers).json()
    assert len(detail["turns"]) == 2
    assert client.get("/support/conversations", headers=auth_headers).json()[0]["id"] == conversation_id


def test_refund_clarification_remembers_question_but_not_payment_amount(client, auth_headers, db_session):
    order = add_order(db_session, current_user(db_session).id)
    conversation_id = create_conversation(client, auth_headers)
    response = ask(client, auth_headers, conversation_id, "我的退款到账了吗？").json()["response"]
    assert response["kind"] == "clarification"
    response = ask(client, auth_headers, conversation_id, str(order.id)).json()["response"]
    assert response["order"]["order_id"] == order.id
    assert "实际到账" in response["answer"]


def test_refund_progress_and_duplicate_application_guidance(client, auth_headers, db_session):
    user_id = current_user(db_session).id
    order = add_order(db_session, user_id, "refund_pending")
    db_session.add(RefundRequest(order_id=order.id, user_id=user_id, amount=Decimal("99"), reason="质量问题",
                                 status="waiting_return", refund_type="return_and_refund"))
    db_session.commit()
    conversation_id = create_conversation(client, auth_headers)
    result = ask(client, auth_headers, conversation_id, f"订单{order.id}退款什么进度").json()["response"]
    assert result["order"]["refund_status_label"] == "等待退货"
    assert "不能重复申请" in result["answer"]


def test_order_and_conversation_isolation(client, auth_headers, db_session):
    other = User(name="另一个用户", age=22, username="other", hashed_password="unused")
    db_session.add(other)
    db_session.commit()
    order = add_order(db_session, other.id)
    conversation_id = create_conversation(client, auth_headers)
    denied = ask(client, auth_headers, conversation_id, f"订单{order.id}发货了吗").json()["response"]
    missing = ask(client, auth_headers, conversation_id, "订单999999发货了吗").json()["response"]
    assert denied == missing
    assert denied["order"] is None
    from app.models.support import SupportConversation
    other_conversation = SupportConversation(id=str(uuid4()), user_id=other.id)
    db_session.add(other_conversation)
    db_session.commit()
    target = other_conversation.id
    assert client.get(f"/support/conversations/{target}", headers=auth_headers).status_code == 404
    assert ask(client, auth_headers, target, "你好").status_code == 404
    assert client.post(f"/support/conversations/{target}/handoff", headers=auth_headers, json={}).status_code == 404


def test_request_retry_is_idempotent_and_conflicting_text_is_rejected(client, auth_headers):
    conversation_id = create_conversation(client, auth_headers)
    request_id = str(uuid4())
    first = ask(client, auth_headers, conversation_id, "我的订单发货了吗", request_id)
    second = ask(client, auth_headers, conversation_id, "我的订单发货了吗", request_id)
    assert first.json() == second.json()
    assert ask(client, auth_headers, conversation_id, "另外一个问题", request_id).status_code == 409


def test_multiple_ids_and_missing_context_ask_for_clarification(client, auth_headers):
    conversation_id = create_conversation(client, auth_headers)
    result = ask(client, auth_headers, conversation_id, "订单1和订单2发货了吗").json()["response"]
    assert "一次提供一个" in result["answer"]
    result = ask(client, auth_headers, conversation_id, "那能退吗").json()["response"]
    assert result["kind"] == "clarification"


def test_knowledge_followup_and_new_topic(client, auth_headers):
    conversation_id = create_conversation(client, auth_headers)
    with patch("app.services.support.answer_supported_question", return_value=SupportAnswer(answer="资料回答", kind="knowledge")) as answer:
        assert ask(client, auth_headers, conversation_id, "已发货如何退款").status_code == 200
        assert ask(client, auth_headers, conversation_id, "那需要满足什么条件").status_code == 200
        assert "已发货如何退款" in answer.call_args.args[1]
        assert "用户追问" in answer.call_args.args[1]
        assert ask(client, auth_headers, conversation_id, "支持哪些支付方式").status_code == 200
        assert answer.call_args.args[1] == "支持哪些支付方式"


def test_rag_failure_still_allows_handoff(client, auth_headers):
    conversation_id = create_conversation(client, auth_headers)
    with patch("app.services.support.answer_supported_question", side_effect=RagServiceUnavailableError()):
        assert ask(client, auth_headers, conversation_id, "配送规则").status_code == 503
    result = client.post(f"/support/conversations/{conversation_id}/handoff", headers=auth_headers,
                         json={"reason": "客服回答失败，请协助"})
    assert result.status_code == 200
    repeated = client.post(f"/support/conversations/{conversation_id}/handoff", headers=auth_headers, json={})
    assert repeated.json()["id"] == result.json()["id"]


def test_ticket_lifecycle_and_admin_authorization(client, auth_headers, db_session):
    conversation_id = create_conversation(client, auth_headers)
    assert ask(client, auth_headers, conversation_id, "帮我转人工").json()["response"]["kind"] == "handoff"
    detail = client.get(f"/support/conversations/{conversation_id}", headers=auth_headers).json()
    ticket_id = detail["ticket"]["id"]
    assert client.get("/admin/support/tickets", headers=auth_headers).status_code == 403
    assert client.get(f"/admin/support/tickets/{ticket_id}", headers=auth_headers).status_code == 403
    assert client.patch(f"/admin/support/tickets/{ticket_id}", headers=auth_headers,
                        json={"status": "resolved", "reply": "回复", "version": 0}).status_code == 403
    user = current_user(db_session)
    user.role = "admin"
    db_session.commit()
    assert client.get("/admin/support/tickets?status=open", headers=auth_headers).json()["total"] == 1
    ticket = client.get(f"/admin/support/tickets/{ticket_id}", headers=auth_headers).json()
    assert len(ticket["turns"]) == 1
    assert client.patch(f"/admin/support/tickets/{ticket_id}", headers=auth_headers,
                        json={"status": "resolved", "version": 0}).status_code == 422
    first = client.patch(f"/admin/support/tickets/{ticket_id}", headers=auth_headers,
                         json={"status": "in_progress", "reply": "正在核查", "version": 0})
    assert first.status_code == 200
    assert client.patch(f"/admin/support/tickets/{ticket_id}", headers=auth_headers,
                        json={"status": "resolved", "reply": "过期编辑", "version": 0}).status_code == 409
    result = client.patch(f"/admin/support/tickets/{ticket_id}", headers=auth_headers,
                          json={"status": "resolved", "reply": "已核查，请到订单页查看", "version": 1})
    assert result.status_code == 200
    final = client.get(f"/support/conversations/{conversation_id}", headers=auth_headers).json()
    assert final["ticket"]["status"] == "resolved"
    assert final["ticket"]["reply"] == "已核查，请到订单页查看"


def test_concurrent_context_change_does_not_save_stale_answer(client, auth_headers, db_session):
    conversation_id = create_conversation(client, auth_headers)
    with patch("app.services.support.repository.advance_conversation", return_value=False):
        assert ask(client, auth_headers, conversation_id, "我的订单发货了吗").status_code == 409
    assert db_session.scalar(select(SupportTurn)) is None


def test_budget_uses_current_products_without_ai(client, auth_headers, db_session):
    from app.models.category import Category
    from app.models.product import Product
    category = Category(name="预算测试")
    db_session.add(category)
    db_session.flush()
    db_session.add_all([
        Product(name="便宜有货", price=Decimal("50"), stock=2, category_id=category.id),
        Product(name="超预算", price=Decimal("150"), stock=2, category_id=category.id),
        Product(name="没有库存", price=Decimal("30"), stock=0, category_id=category.id),
    ])
    db_session.commit()
    conversation_id = create_conversation(client, auth_headers)
    response = ask(client, auth_headers, conversation_id, "推荐100元以内的商品").json()["response"]
    assert response["kind"] == "products"
    assert "便宜有货" in response["answer"]
    assert "超预算" not in response["answer"] and "没有库存" not in response["answer"]


def test_policy_topic_switch_does_not_keep_using_previous_order(client, auth_headers, db_session):
    order = add_order(db_session, current_user(db_session).id)
    conversation_id = create_conversation(client, auth_headers)
    ask(client, auth_headers, conversation_id, f"订单{order.id}发货了吗")
    with patch("app.services.support.answer_supported_question", return_value=SupportAnswer(answer="支付规则", kind="knowledge")) as answer:
        result = ask(client, auth_headers, conversation_id, "那商城支持哪些支付方式").json()["response"]
    assert result["kind"] == "knowledge"
    assert result["order"] is None
    answer.assert_called_once()


def test_declining_handoff_does_not_create_ticket(client, auth_headers):
    conversation_id = create_conversation(client, auth_headers)
    with patch("app.services.support.answer_supported_question", return_value=SupportAnswer(answer="请补充问题", kind="clarification")):
        ask(client, auth_headers, conversation_id, "不要转人工")
    detail = client.get(f"/support/conversations/{conversation_id}", headers=auth_headers).json()
    assert detail["ticket"] is None
