from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.category import Category
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product


def add_payment_test_product(
    db: Session,
) -> int:
    """创建支付测试使用的商品。"""

    category = db.scalar(
        select(Category).where(
            Category.name == "支付测试分类",
        )
    )
    if category is None:
        category = Category(name="支付测试分类")
        db.add(category)
        db.flush()

    product = Product(
        name="支付测试商品",
        price=Decimal("88.00"),
        stock=10,
        description="支付测试",
        category_id=category.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product.id


def create_payment_test_order(
    client: TestClient,
    headers: dict[str, str],
    address_id: int,
    product_id: int,
) -> int:
    """创建待付款测试订单。"""

    response = client.post(
        "/orders/",
        headers=headers,
        json={
            "idempotency_key": f"payment-order-{uuid4().hex}",
            "address_id": address_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 2,
                },
            ],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_payment_record(
    client: TestClient,
    headers: dict[str, str],
    order_id: int,
) -> dict:
    """调用接口创建支付记录。"""

    response = client.post(
        f"/payments/orders/{order_id}",
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def success_callback(
    client: TestClient,
    payment: dict,
    transaction_no: str = "PAYMENT-TEST-001",
):
    """发送模拟支付成功回调。"""

    return client.post(
        "/payments/callback",
        headers={
            "X-Payment-Secret": (
                settings.payment_callback_secret
            ),
        },
        json={
            "payment_id": payment["id"],
            "transaction_no": transaction_no,
            "amount": payment["amount"],
        },
    )


def test_create_payment_is_idempotent(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """重复请求创建支付记录，应返回同一条记录。"""

    product_id = add_payment_test_product(db_session)
    order_id = create_payment_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )

    first = create_payment_record(
        client,
        auth_headers,
        order_id,
    )
    second = create_payment_record(
        client,
        auth_headers,
        order_id,
    )

    assert first["id"] == second["id"]
    assert first["amount"] == "176.00"
    assert first["status"] == "pending"


def test_expired_order_cannot_create_payment(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """待付款订单超过截止时间后，也不能创建支付记录。"""

    product_id = add_payment_test_product(db_session)
    order_id = create_payment_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    order = db_session.get(Order, order_id)
    assert order is not None
    order.expires_at = datetime.now() - timedelta(minutes=1)
    db_session.commit()

    response = client.post(
        f"/payments/orders/{order_id}",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "订单已超过支付期限"}
    assert db_session.scalar(
        select(Payment).where(Payment.order_id == order_id)
    ) is None


def test_payment_fields_are_enforced_by_database(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """即使绕过接口直接改库，支付金额和状态也不能非法。"""

    product_id = add_payment_test_product(db_session)
    order_id = create_payment_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    payment = create_payment_record(
        client,
        auth_headers,
        order_id,
    )

    payment_obj = db_session.get(
        Payment,
        payment["id"],
    )
    assert payment_obj is not None

    payment_obj.amount = Decimal("0")
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    payment_obj = db_session.get(
        Payment,
        payment["id"],
    )
    assert payment_obj is not None

    payment_obj.status = "dfj"
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_user_can_simulate_payment_in_development(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """本地演示接口应把支付和订单更新为成功状态。"""

    product_id = add_payment_test_product(db_session)
    order_id = create_payment_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    payment = create_payment_record(
        client,
        auth_headers,
        order_id,
    )

    response = client.post(
        f"/payments/{payment['id']}/simulate-success",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "success"
    order_response = client.get(
        f"/orders/{order_id}",
        headers=auth_headers,
    )
    assert order_response.json()["status"] == "paid"


def test_simulated_payment_is_disabled_in_production(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """生产环境不能调用本地模拟支付接口。"""

    product_id = add_payment_test_product(db_session)
    order_id = create_payment_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    payment = create_payment_record(
        client,
        auth_headers,
        order_id,
    )
    monkeypatch.setattr(settings, "app_env", "production")

    response = client.post(
        f"/payments/{payment['id']}/simulate-success",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "接口不存在"}


def test_success_callback_is_idempotent_and_marks_order_paid(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """相同成功回调重复到达时，只处理一次。"""

    product_id = add_payment_test_product(db_session)
    order_id = create_payment_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    payment = create_payment_record(
        client,
        auth_headers,
        order_id,
    )

    first_response = success_callback(client, payment)
    second_response = success_callback(client, payment)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["status"] == "success"
    assert second_response.json()["transaction_no"] == (
        "PAYMENT-TEST-001"
    )

    order_response = client.get(
        f"/orders/{order_id}",
        headers=auth_headers,
    )
    assert order_response.json()["status"] == "paid"


def test_expired_order_rejects_payment_success_callback(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """支付记录已创建，但订单后来过期时，成功回调仍应被拒绝。"""

    product_id = add_payment_test_product(db_session)
    order_id = create_payment_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    payment = create_payment_record(
        client,
        auth_headers,
        order_id,
    )
    order = db_session.get(Order, order_id)
    assert order is not None
    order.expires_at = datetime.now() - timedelta(minutes=1)
    db_session.commit()

    response = success_callback(client, payment)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "订单已超过支付期限"}
    payment_response = client.get(
        f"/payments/{payment['id']}",
        headers=auth_headers,
    )
    assert payment_response.json()["status"] == "pending"
    order_response = client.get(
        f"/orders/{order_id}",
        headers=auth_headers,
    )
    assert order_response.json()["status"] == "pending"


def test_callback_rejects_wrong_amount_and_keeps_order_pending(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """回调金额不一致时，不得修改支付和订单状态。"""

    product_id = add_payment_test_product(db_session)
    order_id = create_payment_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    payment = create_payment_record(
        client,
        auth_headers,
        order_id,
    )

    response = client.post(
        "/payments/callback",
        headers={
            "X-Payment-Secret": (
                settings.payment_callback_secret
            ),
        },
        json={
            "payment_id": payment["id"],
            "transaction_no": "WRONG-AMOUNT-001",
            "amount": "1.00",
        },
    )
    assert response.status_code == status.HTTP_409_CONFLICT

    payment_response = client.get(
        f"/payments/{payment['id']}",
        headers=auth_headers,
    )
    assert payment_response.json()["status"] == "pending"

    order_response = client.get(
        f"/orders/{order_id}",
        headers=auth_headers,
    )
    assert order_response.json()["status"] == "pending"


def test_callback_rejects_wrong_secret(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """没有正确内部密钥的请求不能伪造支付回调。"""

    product_id = add_payment_test_product(db_session)
    order_id = create_payment_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    payment = create_payment_record(
        client,
        auth_headers,
        order_id,
    )

    response = client.post(
        "/payments/callback",
        headers={
            "X-Payment-Secret": "wrong-secret",
        },
        json={
            "payment_id": payment["id"],
            "transaction_no": "FORGED-001",
            "amount": payment["amount"],
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
