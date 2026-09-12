from io import BytesIO
from types import SimpleNamespace

from PIL import Image
import pytest

from scripts.seed_demo_products import (
    build_demo_object_name,
    classify_existing_product,
    validate_downloaded_image,
    validate_source_url,
)


def test_build_demo_object_name_is_stable_and_safe() -> None:
    source_url = (
        "https://cdn.dummyjson.com/product-images/"
        "mens-shoes/sports-sneakers-off-white-&-red/thumbnail.webp"
    )

    object_name = build_demo_object_name(source_url)

    assert object_name == (
        "products/demo/dummyjson-v1/mens-shoes/"
        "sports-sneakers-off-white-red.webp"
    )
    assert build_demo_object_name(source_url) == object_name


@pytest.mark.parametrize(
    "source_url",
    [
        "http://cdn.dummyjson.com/product-images/a/b/thumbnail.webp",
        "https://example.com/product-images/a/b/thumbnail.webp",
    ],
)
def test_validate_source_url_rejects_untrusted_sources(
    source_url: str,
) -> None:
    with pytest.raises(ValueError, match="cdn.dummyjson.com"):
        validate_source_url(source_url)


def test_validate_downloaded_image_uses_real_file_format() -> None:
    image_buffer = BytesIO()
    Image.new("RGB", (4, 4), color="white").save(
        image_buffer,
        format="PNG",
    )

    assert validate_downloaded_image(
        image_buffer.getvalue(),
        ".png",
    ) == "image/png"

    with pytest.raises(ValueError, match="实际格式"):
        validate_downloaded_image(
            image_buffer.getvalue(),
            ".webp",
        )


def test_classify_existing_product_preserves_custom_images() -> None:
    source_url = (
        "https://cdn.dummyjson.com/product-images/beauty/item/"
        "thumbnail.webp"
    )
    target_url = (
        "http://127.0.0.1:9000/product-media/"
        "products/demo/dummyjson-v1/beauty/item.webp"
    )

    legacy_product = SimpleNamespace(
        category_id=2,
        image_url=source_url,
    )
    managed_product = SimpleNamespace(
        category_id=2,
        image_url=target_url,
    )
    custom_product = SimpleNamespace(
        category_id=2,
        image_url="http://127.0.0.1:9000/product-media/products/custom.webp",
    )

    assert classify_existing_product([], 2, source_url, target_url) == "create"
    assert classify_existing_product(
        [legacy_product], 2, source_url, target_url
    ) == "migrate"
    assert classify_existing_product(
        [managed_product], 2, source_url, target_url
    ) == "managed"
    assert classify_existing_product(
        [custom_product], 2, source_url, target_url
    ) == "conflict"
