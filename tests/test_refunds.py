from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.order import Order
from app.models.product import Product
from app.models.refund_request import RefundRequest
from app.refund_status import RefundStatus


def add_refund_test_product(
    db: Session,
) -> int:
    """创建退款申请测试商品。"""

    category = db.scalar(
        select(Category).where(
            Category.name == "退款测试分类",
        )
    )
    if category is None:
        category = Category(name="退款测试分类")
        db.add(category)
        db.flush()

    product = Product(
        name="退款测试商品",
        price=Decimal("70.00"),
        stock=10,
        description="退款测试",
        category_id=category.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product.id


def create_refund_test_order(
    client: TestClient,
    headers: dict[str, str],
    address_id: int,
    product_id: int,
) -> int:
    """创建退款测试订单。"""

    response = client.post(
        "/orders/",
        headers=headers,
        json={
            "idempotency_key": f"refund-order-{uuid4().hex}",
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


def test_paid_order_can_create_refund_request(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """已付款未发货订单可以创建退款申请并改变订单状态。"""

    product_id = add_refund_test_product(db_session)
    order_id = create_refund_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    order = db_session.get(Order, order_id)
    assert order is not None
    order.status = "paid"
    db_session.commit()

    response = client.post(
        f"/refunds/orders/{order_id}",
        headers=auth_headers,
        json={
            "reason": "  不再需要该商品  ",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["order_id"] == order_id
    assert response.json()["amount"] == "140.00"
    assert response.json()["reason"] == "不再需要该商品"
    assert response.json()["status"] == "pending"

    db_session.expire_all()
    assert db_session.get(Order, order_id).status == "refund_pending"

    list_response = client.get(
        "/refunds/",
        headers=auth_headers,
    )
    assert list_response.status_code == status.HTTP_200_OK
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["order_id"] == order_id

    refund_id = response.json()["id"]
    refund_request = db_session.get(
        RefundRequest,
        refund_id,
    )
    assert refund_request is not None

    # 暂时模拟管理员已经同意用户退货。
    refund_request.status = RefundStatus.WAITING_RETURN
    db_session.commit()

    tracking_response = client.patch(
        f"/refunds/{refund_id}/return-tracking",
        headers=auth_headers,
        json={
            "company": "顺丰速运",
            "tracking_number": "SF123456789",
        },
    )

    assert tracking_response.status_code == status.HTTP_200_OK
    assert tracking_response.json()["return_company"] == "顺丰速运"
    assert (
        tracking_response.json()["return_tracking_number"]
        == "SF123456789"
    )
    assert tracking_response.json()["status"] == "returning"

    db_session.expire_all()
    saved_refund = db_session.get(
        RefundRequest,
        refund_id,
    )
    assert saved_refund is not None
    assert saved_refund.return_company == "顺丰速运"
    assert saved_refund.return_tracking_number == "SF123456789"
    assert saved_refund.status == RefundStatus.RETURNING


def test_refund_fields_are_enforced_by_database(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """即使绕过接口直接改库，退款金额、状态和类型也不能非法。"""

    product_id = add_refund_test_product(db_session)
    order_id = create_refund_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    order = db_session.get(Order, order_id)
    assert order is not None
    order.status = "paid"
    db_session.commit()

    response = client.post(
        f"/refunds/orders/{order_id}",
        headers=auth_headers,
        json={"reason": "商品不合适"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    refund_id = response.json()["id"]

    refund_request = db_session.get(
        RefundRequest,
        refund_id,
    )
    assert refund_request is not None

    refund_request.amount = Decimal("0")
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    refund_request = db_session.get(
        RefundRequest,
        refund_id,
    )
    assert refund_request is not None

    refund_request.status = "dfj"
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    refund_request = db_session.get(
        RefundRequest,
        refund_id,
    )
    assert refund_request is not None

    refund_request.refund_type = "dfj"
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_pending_order_cannot_create_refund_request(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """尚未付款的订单不能申请退款。"""

    product_id = add_refund_test_product(db_session)
    order_id = create_refund_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )

    response = client.post(
        f"/refunds/orders/{order_id}",
        headers=auth_headers,
        json={"reason": "不再需要"},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "仅退款只适用于已付款未发货订单",
    }


def test_user_cannot_refund_other_users_order(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """用户不能为其他用户的订单申请退款。"""

    product_id = add_refund_test_product(db_session)
    order_id = create_refund_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )
    order = db_session.get(Order, order_id)
    assert order is not None
    order.status = "paid"
    db_session.commit()

    register_response = client.post(
        "/auth/register",
        json={
            "name": "其他退款用户",
            "age": 20,
            "username": "other_refund_user",
            "password": "abc123456",
        },
    )
    assert register_response.status_code == 201
    login_response = client.post(
        "/auth/login",
        data={
            "username": "other_refund_user",
            "password": "abc123456",
        },
    )
    other_headers = {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }

    response = client.post(
        f"/refunds/orders/{order_id}",
        headers=other_headers,
        json={"reason": "尝试退款"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_pending_refund_cannot_submit_return_tracking(
    client: TestClient,
    auth_headers: dict[str, str],
    shipping_address_id: int,
    db_session: Session,
) -> None:
    """等待审核的退款不能提交退货物流。"""

    product_id = add_refund_test_product(db_session)
    order_id = create_refund_test_order(
        client,
        auth_headers,
        shipping_address_id,
        product_id,
    )

    order = db_session.get(Order, order_id)
    assert order is not None
    order.status = "paid"
    db_session.commit()

    create_response = client.post(
        f"/refunds/orders/{order_id}",
        headers=auth_headers,
        json={"reason": "商品不合适"},
    )
    assert create_response.status_code == status.HTTP_201_CREATED

    refund_id = create_response.json()["id"]

    tracking_response = client.patch(
        f"/refunds/{refund_id}/return-tracking",
        headers=auth_headers,
        json={
            "company": "顺丰速运",
            "tracking_number": "SF123456789",
        },
    )

    assert tracking_response.status_code == status.HTTP_409_CONFLICT
    assert tracking_response.json() == {
        "detail": "当前退款状态不能填写退货物流",
    }

    db_session.expire_all()
    saved_refund = db_session.get(
        RefundRequest,
        refund_id,
    )
    assert saved_refund is not None
    assert saved_refund.status == RefundStatus.PENDING
    assert saved_refund.return_company is None
    assert saved_refund.return_tracking_number is None
