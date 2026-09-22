from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.rag_product_sync_task import RagProductSyncTask


@pytest.mark.parametrize("fail_task_insert", [False, True])
def test_product_and_sync_task_share_transaction(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
    fail_task_insert: bool,
) -> None:
    """任务插入成功则共同保存，插入失败则撤销已经flush的商品。"""
    response = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "同步任务事务测试分类"},
    )
    assert response.status_code == 201
    category_id = response.json()["id"]

    def reject_task_insert(mapper, connection, target):
        # target：即将插入的任务，已取得商品的真实ID
        assert target.product_id > 0
        raise SQLAlchemyError("simulated task insert failure")

    if fail_task_insert:
        event.listen(RagProductSyncTask, "before_insert", reject_task_insert)
    try:
        response = client.post(
            "/products/",
            headers=admin_headers,
            json={
                "name": "待同步耳机",
                "price": 399,
                "stock": 5,
                "category_id": category_id,
            },
        )
    finally:
        if fail_task_insert:
            event.remove(RagProductSyncTask, "before_insert", reject_task_insert)

    products = db_session.scalars(select(Product)).all()
    tasks = db_session.scalars(select(RagProductSyncTask)).all()
    if fail_task_insert:
        assert response.status_code == 500
        assert response.json() == {"detail": "商品保存失败"}
        assert products == []
        assert tasks == []
    else:
        assert response.status_code == 201
        assert len(products) == len(tasks) == 1
        assert tasks[0].product_id == products[0].id == response.json()["id"]
        assert tasks[0].operation == "upsert"
        assert tasks[0].status == "pending"


@pytest.mark.parametrize(
    "changes, fail_task_insert, expected_price, expected_tasks",
    [
        ({}, False, "399", 1),
        ({"price": 499}, False, "499", 2),
        ({"price": 399}, False, "399", 2),
        ({"price": 499}, True, "399", 1),
    ],
)
def test_product_update_and_sync_task_share_transaction(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
    changes: dict[str, int],
    fail_task_insert: bool,
    expected_price: str,
    expected_tasks: int,
) -> None:
    """空请求由Schema拒绝；有字段则创建任务，保存失败时回滚价格。"""
    category = client.post(
        "/categories/",
        headers=admin_headers,
        json={"name": "商品更新事务测试分类"},
    )
    assert category.status_code == 201
    created = client.post(
        "/products/",
        headers=admin_headers,
        json={
            "name": "更新测试耳机",
            "price": 399,
            "stock": 5,
            "category_id": category.json()["id"],
        },
    )
    assert created.status_code == 201
    product_id = created.json()["id"]

    def reject_task_insert(mapper, connection, target):
        raise SQLAlchemyError("simulated task insert failure")

    if fail_task_insert:
        event.listen(RagProductSyncTask, "before_insert", reject_task_insert)
    try:
        response = client.patch(
            f"/products/{product_id}",
            headers=admin_headers,
            json=changes,
        )
    finally:
        if fail_task_insert:
            event.remove(RagProductSyncTask, "before_insert", reject_task_insert)

    expected_status = 422 if not changes else (500 if fail_task_insert else 200)
    assert response.status_code == expected_status
    if fail_task_insert:
        assert response.json() == {"detail": "商品更新失败"}
    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.price == Decimal(expected_price)
    tasks = db_session.scalars(select(RagProductSyncTask)).all()
    assert len(tasks) == expected_tasks
    assert all(task.product_id == product_id for task in tasks)
    assert all(task.operation == "upsert" and task.status == "pending" for task in tasks)


@pytest.mark.parametrize("fail_task_insert", [False, True])
def test_product_delete_and_sync_task_share_transaction(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
    fail_task_insert: bool,
) -> None:
    """删除商品后保留删除任务；任务插入失败时保留商品。"""
    category = client.post(
        "/categories/", headers=admin_headers,
        json={"name": "删除同步事务分类"},
    )
    assert category.status_code == 201
    created = client.post(
        "/products/", headers=admin_headers,
        json={"name": "待删除耳机", "price": 399, "stock": 5,
              "category_id": category.json()["id"]},
    )
    assert created.status_code == 201
    product_id = created.json()["id"]

    def reject_task_insert(mapper, connection, target):
        assert target.operation == "delete"
        raise SQLAlchemyError("simulated deletion task insert failure")

    if fail_task_insert:
        event.listen(RagProductSyncTask, "before_insert", reject_task_insert)
    try:
        response = client.delete(f"/products/{product_id}", headers=admin_headers)
    finally:
        if fail_task_insert:
            event.remove(RagProductSyncTask, "before_insert", reject_task_insert)

    product = db_session.get(Product, product_id)
    tasks = db_session.scalars(
        select(RagProductSyncTask).order_by(RagProductSyncTask.id)
    ).all()
    if fail_task_insert:
        assert response.status_code == 500
        assert response.json() == {"detail": "商品删除失败"}
        assert product is not None
        assert len(tasks) == 1
        assert tasks[0].operation == "upsert"
    else:
        assert response.status_code == 204
        assert product is None
        assert len(tasks) == 2
        assert tasks[-1].product_id == product_id
        assert tasks[-1].operation == "delete"
        assert tasks[-1].status == "pending"
