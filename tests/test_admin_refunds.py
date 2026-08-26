from decimal import Decimal

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.category import Category
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.refund_request import RefundRequest


def add_admin_refund_product(
    db: Session,
) -> int:
    """创建管理员退款测试商品。"""

    category = db.scalar(
        select(Category).where(
            Category.name == "管理员退款测试分类",
        )
    )
    if category is None:
        category = Category(
            name="管理员退款测试分类",
        )
        db.add(category)
        db.flush()

    product = Product(
        name="管理员退款测试商品",
        price=Decimal("80.00"),
        stock=10,
        description="管理员退款测试",
        category_id=category.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product.id


def create_paid_order_and_refund(
    client: TestClient,
    headers: dict[str, str],
    address_id: int,
    product_id: int,
) -> tuple[int, int]:
    """通过真实接口创建已付款订单和待审核退款申请。"""

    order_response = client.post(
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
    assert order_response.status_code == 201
    order_id = order_response.json()["id"]

    payment_response = client.post(
        f"/payments/orders/{order_id}",
        headers=headers,
    )
    assert payment_response.status_code == 201
    payment = payment_response.json()

    callback_response = client.post(
        "/payments/callback",
        headers={
            "X-Payment-Secret": (
                settings.payment_callback_secret
            ),
        },
        json={
            "payment_id": payment["id"],
            "transaction_no": f"REFUND-PAY-{order_id}",
            "amount": payment["amount"],
        },
    )
    assert callback_response.status_code == 200

    refund_response = client.post(
        f"/refunds/orders/{order_id}",
        headers=headers,
        json={
            "reason": "未发货申请退款",
        },
    )
    assert refund_response.status_code == 201
    return order_id, refund_response.json()["id"]


def test_admin_approval_refunds_order_and_restores_stock(
    client: TestClient,
    admin_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """批准退款应同步状态、审核信息和库存。"""

    product_id = add_admin_refund_product(db_session)
    order_id, refund_id = create_paid_order_and_refund(
        client,
        admin_headers,
        shipping_address_id,
        product_id,
    )

    db_session.expire_all()
    assert db_session.get(Product, product_id).stock == 8

    response = client.post(
        f"/admin/refunds/{refund_id}/approve",
        headers=admin_headers,
        json={
            "review_note": "符合未发货退款条件",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["review_note"] == "符合未发货退款条件"
    assert response.json()["reviewer_id"] is not None
    assert response.json()["reviewed_at"] is not None

    db_session.expire_all()
    order = db_session.get(Order, order_id)
    payment = db_session.scalar(
        select(Payment).where(
            Payment.order_id == order_id,
        )
    )
    refund = db_session.get(RefundRequest, refund_id)

    assert order is not None
    assert payment is not None
    assert refund is not None
    assert order.status == "refunded"
    assert payment.status == "refunded"
    assert refund.status == "approved"
    assert db_session.get(Product, product_id).stock == 10

    repeated_response = client.post(
        f"/admin/refunds/{refund_id}/approve",
        headers=admin_headers,
        json={},
    )
    assert repeated_response.status_code == status.HTTP_409_CONFLICT

    db_session.expire_all()
    assert db_session.get(Product, product_id).stock == 10


def test_regular_user_cannot_approve_refund(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """普通用户不能调用管理员退款批准接口。"""

    response = client.post(
        "/admin/refunds/1/approve",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_rejection_keeps_payment_and_stock(
    client: TestClient,
    admin_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """拒绝退款应恢复订单状态，但不改变支付状态和库存。"""

    product_id = add_admin_refund_product(db_session)
    order_id, refund_id = create_paid_order_and_refund(
        client,
        admin_headers,
        shipping_address_id,
        product_id,
    )

    db_session.expire_all()
    assert db_session.get(Product, product_id).stock == 8

    response = client.post(
        f"/admin/refunds/{refund_id}/reject",
        headers=admin_headers,
        json={
            "review_note": "不符合退款条件",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "rejected"
    assert response.json()["review_note"] == "不符合退款条件"
    assert response.json()["reviewer_id"] is not None
    assert response.json()["reviewed_at"] is not None

    db_session.expire_all()
    order = db_session.get(Order, order_id)
    payment = db_session.scalar(
        select(Payment).where(
            Payment.order_id == order_id,
        )
    )
    refund = db_session.get(RefundRequest, refund_id)

    assert order is not None
    assert payment is not None
    assert refund is not None
    assert order.status == "paid"
    assert payment.status == "success"
    assert refund.status == "rejected"
    assert db_session.get(Product, product_id).stock == 8

    repeated_response = client.post(
        f"/admin/refunds/{refund_id}/reject",
        headers=admin_headers,
        json={},
    )
    assert repeated_response.status_code == status.HTTP_409_CONFLICT

    db_session.expire_all()
    assert db_session.get(Product, product_id).stock == 8


def test_admin_can_filter_and_paginate_refunds(
    client: TestClient,
    admin_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """管理员可按申请人、状态筛选退款并进行分页。"""

    first_product_id = add_admin_refund_product(db_session)
    second_product_id = add_admin_refund_product(db_session)
    _, first_refund_id = create_paid_order_and_refund(
        client,
        admin_headers,
        shipping_address_id,
        first_product_id,
    )
    _, second_refund_id = create_paid_order_and_refund(
        client,
        admin_headers,
        shipping_address_id,
        second_product_id,
    )

    approve_response = client.post(
        f"/admin/refunds/{first_refund_id}/approve",
        headers=admin_headers,
        json={},
    )
    assert approve_response.status_code == status.HTTP_200_OK

    db_session.expire_all()
    first_refund = db_session.get(
        RefundRequest,
        first_refund_id,
    )
    assert first_refund is not None

    user_response = client.get(
        "/admin/refunds",
        headers=admin_headers,
        params={
            "user_id": first_refund.user_id,
        },
    )
    assert user_response.status_code == status.HTTP_200_OK
    assert user_response.json()["total"] == 2

    status_response = client.get(
        "/admin/refunds",
        headers=admin_headers,
        params={
            "status": "pending",
        },
    )
    assert status_response.status_code == status.HTTP_200_OK
    assert status_response.json()["total"] == 1
    assert status_response.json()["items"][0]["id"] == second_refund_id

    page_response = client.get(
        "/admin/refunds",
        headers=admin_headers,
        params={
            "skip": 1,
            "limit": 1,
        },
    )
    assert page_response.status_code == status.HTTP_200_OK
    assert page_response.json()["total"] == 2
    assert page_response.json()["skip"] == 1
    assert page_response.json()["limit"] == 1
    assert len(page_response.json()["items"]) == 1
    assert page_response.json()["items"][0]["id"] == first_refund_id


def test_regular_user_cannot_list_refunds(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """普通用户不能查看管理员退款申请列表。"""

    response = client.get(
        "/admin/refunds",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
