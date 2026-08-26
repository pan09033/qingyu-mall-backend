from fastapi.testclient import TestClient


def test_root(
    client: TestClient,
) -> None:
    """根接口应返回 200 和预期的 JSON 内容。"""

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "用户和商品管理系统运行成功",
    }
