from fastapi import APIRouter, Depends, UploadFile, status

from app.dependencies import get_current_admin
from app.services.media import (
    build_public_object_url,
    upload_product_image,
)


router = APIRouter(
    prefix="/media",
    tags=["媒体管理"],
)


@router.post(
    "/product-images",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
def upload_image(file: UploadFile) -> dict[str, str]:
    object_name = upload_product_image(file)

    image_url = build_public_object_url(object_name)

    return {
        "object_name": object_name,
        "image_url": image_url,
    }
