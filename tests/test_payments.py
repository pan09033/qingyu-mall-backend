from decimal import Decimal

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.category import Category
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
