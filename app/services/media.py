from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from uuid import uuid4
from app.config import settings
from app.storage import get_minio_client
from minio.error import S3Error
from urllib3.exceptions import HTTPError

MAX_IMAGE_SIZE = 10 * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def validate_image_upload(file: UploadFile) -> str:
    if file.size is None or file.size == 0:
        raise HTTPException(
            status_code=400,
            detail="文件为空或无法确定大小",
        )

    if file.size > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="图片不能超过 10 MiB",
        )

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="只支持 JPEG、PNG、WebP 图片",
        )

    expected_formats = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }

    try:
        file.file.seek(0)

        with Image.open(file.file) as image:
            if image.format != expected_formats[file.content_type]:
                raise HTTPException(
                    status_code=415,
                    detail="图片实际格式与声明类型不一致",
                )

            image.verify()

    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise HTTPException(
            status_code=400,
            detail="图片内容无效或文件已损坏",
        ) from error

    finally:
        file.file.seek(0)

    return ALLOWED_IMAGE_TYPES[file.content_type]


def upload_product_image(file: UploadFile) -> str:
    extension = validate_image_upload(file)

    object_name = f"products/{uuid4().hex}{extension}"

    client = get_minio_client()
    try:
        client.put_object(
            bucket_name=settings.minio_bucket,
            object_name=object_name,
            data=file.file,
            length=file.size,
            content_type=file.content_type,
        )
    except (S3Error, HTTPError, OSError) as error:
        raise HTTPException(
            status_code=503,
            detail="图片存储服务暂时不可用，请稍后重试",
        ) from error

    return object_name


def build_public_object_url(object_name: str) -> str:
    base_url = settings.minio_public_base_url.rstrip("/")

    return (
        f"{base_url}/"
        f"{settings.minio_bucket}/"
        f"{object_name}"
    )
