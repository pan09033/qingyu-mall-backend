from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.services import media as media_service


def create_png_bytes() -> bytes:
    """在内存中创建有效 PNG，测试不会读取本地图片。"""

    output = BytesIO()
    Image.new("RGB", (2, 2), color="blue").save(
        output,
        format="PNG",
    )
    return output.getvalue()


def test_regular_user_cannot_upload_product_image(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """普通用户不能调用管理员商品图片上传接口。"""

    minio_client = Mock()
    monkeypatch.setattr(
        media_service,
        "get_minio_client",
        lambda: minio_client,
    )

    response = client.post(
        "/media/product-images",
        headers=auth_headers,
        files={
            "file": (
                "product.png",
                create_png_bytes(),
                "image/png",
            ),
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    minio_client.put_object.assert_not_called()


def test_admin_can_upload_product_image(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """管理员上传有效图片后获得对象名称和公开地址。"""

    image_content = create_png_bytes()
    minio_client = Mock()
    monkeypatch.setattr(
        media_service,
        "get_minio_client",
        lambda: minio_client,
    )

    response = client.post(
        "/media/product-images",
        headers=admin_headers,
        files={
            "file": (
                "product.png",
                image_content,
                "image/png",
            ),
        },
    )

    assert response.status_code == status.HTTP_201_CREATED

    response_data = response.json()
    object_name = response_data["object_name"]
    assert object_name.startswith("products/")
    assert object_name.endswith(".png")
    assert response_data["image_url"] == (
        f"{settings.minio_public_base_url.rstrip('/')}"
        f"/{settings.minio_bucket}/{object_name}"
    )

    minio_client.put_object.assert_called_once()
    upload_arguments = minio_client.put_object.call_args.kwargs
    assert upload_arguments["bucket_name"] == settings.minio_bucket
    assert upload_arguments["object_name"] == object_name
    assert upload_arguments["length"] == len(image_content)
    assert upload_arguments["content_type"] == "image/png"


def test_admin_cannot_upload_unsupported_file_type(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """后端拒绝不在允许列表中的文件类型。"""

    response = client.post(
        "/media/product-images",
        headers=admin_headers,
        files={
            "file": (
                "notes.txt",
                b"not an image",
                "text/plain",
            ),
        },
    )

    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert response.json() == {
        "detail": "只支持 JPEG、PNG、WebP 图片",
    }


def test_admin_cannot_disguise_text_as_png(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """即使声明为 PNG，实际内容不是图片时也会被拒绝。"""

    response = client.post(
        "/media/product-images",
        headers=admin_headers,
        files={
            "file": (
                "fake.png",
                b"this is plain text",
                "image/png",
            ),
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "detail": "图片内容无效或文件已损坏",
    }


def test_upload_returns_503_when_minio_is_unavailable(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """存储异常被转换为稳定的 HTTP 503 响应。"""

    minio_client = Mock()
    minio_client.put_object.side_effect = OSError(
        "MinIO unavailable",
    )
    monkeypatch.setattr(
        media_service,
        "get_minio_client",
        lambda: minio_client,
    )

    response = client.post(
        "/media/product-images",
        headers=admin_headers,
        files={
            "file": (
                "product.png",
                create_png_bytes(),
                "image/png",
            ),
        },
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {
        "detail": "图片存储服务暂时不可用，请稍后重试",
    }
