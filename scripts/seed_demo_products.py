"""把商城演示商品及其主图同步到本地 MySQL 与 MinIO。

数据基于 DummyJSON 的公开占位商品整理：
https://dummyjson.com/docs/products

运行方式：
    python -m scripts.seed_demo_products --dry-run
    python -m scripts.seed_demo_products

脚本使用确定性的 MinIO Object Key，可以安全地重复执行。只有仍然
指向清单中 DummyJSON 原地址的旧演示商品会被迁移；手工维护的同名
商品及图片不会被覆盖。
"""

from argparse import ArgumentParser
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO
from pathlib import PurePosixPath
import re
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from minio import Minio
from minio.error import S3Error
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine
from app.models.category import Category
from app.models.product import Product
from app.product_cache import invalidate_product_cache
from app.schemas.product import ProductCreate
from app.services.media import MAX_IMAGE_SIZE, build_public_object_url
from app.storage import get_minio_client


SOURCE_IMAGE_HOST = "cdn.dummyjson.com"
ALLOWED_SOURCE_HOSTS = {SOURCE_IMAGE_HOST}
DEMO_OBJECT_PREFIX = "products/demo/dummyjson-v1"
DOWNLOAD_TIMEOUT_SECONDS = 20
MISSING_OBJECT_CODES = {"NoSuchKey", "NoSuchObject"}
IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


CATEGORY_SPECS = {
    "美妆护理": "彩妆、护肤与个人护理好物。",
    "家居生活": "卧室、客厅与办公空间的实用家具。",
    "食品生鲜": "日常水果、肉类与宠物食品。",
    "数码电脑": "适合学习、办公和创作的数码设备。",
    "运动户外": "球类运动与日常训练装备。",
    "鞋履穿搭": "兼顾舒适度与设计感的日常鞋履。",
}


PRODUCT_SPECS = [
    {
        "name": "纤长浓密睫毛膏",
        "price": "79.00",
        "stock": 99,
        "description": "轻盈膏体兼顾纤长与浓密效果，适合打造清晰自然的日常眼妆。",
        "image_url": "https://cdn.dummyjson.com/product-images/beauty/essence-mascara-lash-princess/thumbnail.webp",
        "category": "美妆护理",
    },
    {
        "name": "便携镜面多色眼影盘",
        "price": "129.00",
        "stock": 34,
        "description": "多种日常配色搭配内置镜面，通勤、旅行时补妆更加方便。",
        "image_url": "https://cdn.dummyjson.com/product-images/beauty/eyeshadow-palette-with-mirror/thumbnail.webp",
        "category": "美妆护理",
    },
    {
        "name": "轻盈控油定妆散粉",
        "price": "99.00",
        "stock": 89,
        "description": "细腻透明粉质帮助控制面部油光，呈现轻盈自然的哑光妆效。",
        "image_url": "https://cdn.dummyjson.com/product-images/beauty/powder-canister/thumbnail.webp",
        "category": "美妆护理",
    },
    {
        "name": "经典丝绒红色口红",
        "price": "109.00",
        "stock": 91,
        "description": "显色饱满的经典红色，顺滑质地兼顾舒适度与持妆表现。",
        "image_url": "https://cdn.dummyjson.com/product-images/beauty/red-lipstick/thumbnail.webp",
        "category": "美妆护理",
    },
    {
        "name": "意式软包双人床",
        "price": "2899.00",
        "stock": 18,
        "description": "简洁软包造型搭配稳固床架，为卧室提供舒适而克制的视觉焦点。",
        "image_url": "https://cdn.dummyjson.com/product-images/furniture/annibale-colombo-bed/thumbnail.webp",
        "category": "家居生活",
    },
    {
        "name": "意式客厅三人沙发",
        "price": "3999.00",
        "stock": 12,
        "description": "宽大坐深与柔软包覆感兼备，适合客厅阅读、休息与家庭交流。",
        "image_url": "https://cdn.dummyjson.com/product-images/furniture/annibale-colombo-sofa/thumbnail.webp",
        "category": "家居生活",
    },
    {
        "name": "樱桃木色床头柜",
        "price": "599.00",
        "stock": 64,
        "description": "温润木色与实用储物空间结合，可收纳睡前读物和日常小物。",
        "image_url": "https://cdn.dummyjson.com/product-images/furniture/bedside-table-african-cherry/thumbnail.webp",
        "category": "家居生活",
    },
    {
        "name": "人体工学会议椅",
        "price": "1299.00",
        "stock": 26,
        "description": "流畅椅背与稳定支撑结构，适合会议室、书房和日常办公场景。",
        "image_url": "https://cdn.dummyjson.com/product-images/furniture/knoll-saarinen-executive-conference-chair/thumbnail.webp",
        "category": "家居生活",
    },
    {
        "name": "脆甜红苹果",
        "price": "12.90",
        "stock": 80,
        "description": "果肉清脆、酸甜平衡，可直接食用，也适合制作沙拉和烘焙点心。",
        "image_url": "https://cdn.dummyjson.com/product-images/groceries/apple/thumbnail.webp",
        "category": "食品生鲜",
    },
    {
        "name": "家庭装原切牛排",
        "price": "89.00",
        "stock": 46,
        "description": "纹理清晰、肉质厚实，适合煎制、烧烤或搭配蔬菜制作正餐。",
        "image_url": "https://cdn.dummyjson.com/product-images/groceries/beef-steak/thumbnail.webp",
        "category": "食品生鲜",
    },
    {
        "name": "全价营养猫粮",
        "price": "59.00",
        "stock": 46,
        "description": "为成年猫日常饮食设计的均衡配方，请根据宠物体重合理控制喂食量。",
        "image_url": "https://cdn.dummyjson.com/product-images/groceries/cat-food/thumbnail.webp",
        "category": "食品生鲜",
    },
    {
        "name": "鲜嫩鸡胸肉",
        "price": "39.00",
        "stock": 97,
        "description": "肉质细嫩、烹饪方式多样，适合煎炒、炖煮和轻食搭配。",
        "image_url": "https://cdn.dummyjson.com/product-images/groceries/chicken-meat/thumbnail.webp",
        "category": "食品生鲜",
    },
    {
        "name": "MacBook Pro 14英寸",
        "price": "12999.00",
        "stock": 24,
        "description": "深空灰机身搭配高分辨率屏幕，适合移动办公、编程和内容创作。",
        "image_url": "https://cdn.dummyjson.com/product-images/laptops/apple-macbook-pro-14-inch-space-grey/thumbnail.webp",
        "category": "数码电脑",
    },
    {
        "name": "华硕灵耀双屏笔记本",
        "price": "11999.00",
        "stock": 45,
        "description": "双屏交互设计为多任务处理和创意工作提供更灵活的桌面空间。",
        "image_url": "https://cdn.dummyjson.com/product-images/laptops/asus-zenbook-pro-dual-screen-laptop/thumbnail.webp",
        "category": "数码电脑",
    },
    {
        "name": "华为 MateBook X Pro",
        "price": "8999.00",
        "stock": 75,
        "description": "轻薄金属机身搭配高分辨率触控屏，满足通勤和移动办公需求。",
        "image_url": "https://cdn.dummyjson.com/product-images/laptops/huawei-matebook-x-pro/thumbnail.webp",
        "category": "数码电脑",
    },
    {
        "name": "联想 Yoga 920 二合一",
        "price": "7499.00",
        "stock": 40,
        "description": "可翻转铰链支持笔记本和平板形态，兼顾便携性与多场景使用。",
        "image_url": "https://cdn.dummyjson.com/product-images/laptops/lenovo-yoga-920/thumbnail.webp",
        "category": "数码电脑",
    },
    {
        "name": "美式橄榄球",
        "price": "129.00",
        "stock": 53,
        "description": "经典球体造型与防滑纹理，适合传接球训练和户外团队活动。",
        "image_url": "https://cdn.dummyjson.com/product-images/sports-accessories/american-football/thumbnail.webp",
        "category": "运动户外",
    },
    {
        "name": "耐磨训练棒球",
        "price": "39.00",
        "stock": 100,
        "description": "耐磨球面与标准尺寸设计，可用于日常投球、击球和接球训练。",
        "image_url": "https://cdn.dummyjson.com/product-images/sports-accessories/baseball-ball/thumbnail.webp",
        "category": "运动户外",
    },
    {
        "name": "专业接球棒球手套",
        "price": "159.00",
        "stock": 22,
        "description": "贴合手型的接球结构，提供稳定包裹感和训练时所需的操控性。",
        "image_url": "https://cdn.dummyjson.com/product-images/sports-accessories/baseball-glove/thumbnail.webp",
        "category": "运动户外",
    },
    {
        "name": "室内外通用篮球",
        "price": "99.00",
        "stock": 75,
        "description": "兼顾抓握感与耐磨表现，适用于室内球馆和常见室外场地。",
        "image_url": "https://cdn.dummyjson.com/product-images/sports-accessories/basketball/thumbnail.webp",
        "category": "运动户外",
    },
    {
        "name": "Air Jordan 1 红黑运动鞋",
        "price": "1299.00",
        "stock": 7,
        "description": "经典红黑撞色与高帮轮廓结合，适合日常街头穿搭和鞋款收藏。",
        "image_url": "https://cdn.dummyjson.com/product-images/mens-shoes/nike-air-jordan-1-red-and-black/thumbnail.webp",
        "category": "鞋履穿搭",
    },
    {
        "name": "Nike 棒球训练钉鞋",
        "price": "699.00",
        "stock": 12,
        "description": "针对球场抓地需求设计，为跑动、启动和方向变化提供稳定支撑。",
        "image_url": "https://cdn.dummyjson.com/product-images/mens-shoes/nike-baseball-cleats/thumbnail.webp",
        "category": "鞋履穿搭",
    },
    {
        "name": "PUMA Future Rider 休闲鞋",
        "price": "599.00",
        "stock": 90,
        "description": "复古鞋型结合轻便脚感，适合通勤、散步和日常休闲穿搭。",
        "image_url": "https://cdn.dummyjson.com/product-images/mens-shoes/puma-future-rider-trainers/thumbnail.webp",
        "category": "鞋履穿搭",
    },
    {
        "name": "米白红拼色运动鞋",
        "price": "499.00",
        "stock": 17,
        "description": "米白鞋面点缀红色细节，兼顾运动感与日常搭配的轻松氛围。",
        "image_url": "https://cdn.dummyjson.com/product-images/mens-shoes/sports-sneakers-off-white-&-red/thumbnail.webp",
        "category": "鞋履穿搭",
    },
    {
        "name": "木质浴室台盆镜面组合",
        "price": "799.99",
        "stock": 7,
        "description": "木质台盆搭配同款镜面，为浴室带来温暖自然的收纳与洗漱空间。",
        "image_url": "https://cdn.dummyjson.com/product-images/furniture/wooden-bathroom-sink-with-mirror/thumbnail.webp",
        "category": "家居生活",
    },
    {
        "name": "现代简约台灯",
        "price": "49.99",
        "stock": 9,
        "description": "简洁灯体兼顾氛围与阅读照明，适合卧室床头或日常办公桌面。",
        "image_url": "https://cdn.dummyjson.com/product-images/home-decoration/table-lamp/thumbnail.webp",
        "category": "家居生活",
    },
    {
        "name": "环保竹制锅铲",
        "price": "7.99",
        "stock": 37,
        "description": "轻巧竹材锅铲适合翻炒、搅拌与盛菜，日常使用握持自然。",
        "image_url": "https://cdn.dummyjson.com/product-images/kitchen-accessories/bamboo-spatula/thumbnail.webp",
        "category": "家居生活",
    },
    {
        "name": "原味天然蜂蜜",
        "price": "6.99",
        "stock": 34,
        "description": "瓶装天然蜂蜜口感清甜，适合冲饮、搭配早餐或制作甜品。",
        "image_url": "https://cdn.dummyjson.com/product-images/groceries/honey-jar/thumbnail.webp",
        "category": "食品生鲜",
    },
    {
        "name": "折叠伸缩自拍杆",
        "price": "12.99",
        "stock": 11,
        "description": "可折叠伸缩结构便于随身携带，适合手机自拍、合影和旅行记录。",
        "image_url": "https://cdn.dummyjson.com/product-images/mobile-accessories/selfie-stick-monopod/thumbnail.webp",
        "category": "数码电脑",
    },
    {
        "name": "iPhone 13 Pro",
        "price": "1099.99",
        "stock": 56,
        "description": "高性能芯片搭配专业影像系统与高刷新率屏幕，满足日常和创作需求。",
        "image_url": "https://cdn.dummyjson.com/product-images/smartphones/iphone-13-pro/thumbnail.webp",
        "category": "数码电脑",
    },
    {
        "name": "蓝黑格纹男士衬衫",
        "price": "29.99",
        "stock": 38,
        "description": "经典蓝黑格纹与利落版型结合，适合休闲通勤和半正式场合。",
        "image_url": "https://cdn.dummyjson.com/product-images/mens-shirts/blue-&-black-check-shirt/thumbnail.webp",
        "category": "鞋履穿搭",
    },
    {
        "name": "波点休闲连衣裙",
        "price": "49.99",
        "stock": 6,
        "description": "轻松活泼的印花设计兼顾舒适度，适合日常出行与周末休闲穿着。",
        "image_url": "https://cdn.dummyjson.com/product-images/womens-dresses/dress-pea/thumbnail.webp",
        "category": "鞋履穿搭",
    },
]


@dataclass
class SeedSummary:
    """一次同步的统计结果。"""

    created_categories: int = 0
    created_products: int = 0
    migrated_products: int = 0
    unchanged_products: int = 0
    conflict_products: int = 0
    uploaded_objects: int = 0
    reused_objects: int = 0
    conflicts: list[str] = field(default_factory=list)


def validate_source_url(source_url: str) -> None:
    """只允许下载清单中约定的 DummyJSON HTTPS 图片。"""

    parsed_url = urlsplit(source_url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname not in ALLOWED_SOURCE_HOSTS
    ):
        raise ValueError(
            "演示图片只能来自 cdn.dummyjson.com 的 HTTPS 地址"
        )


def build_demo_object_name(source_url: str) -> str:
    """把来源 URL 转换为可重复使用的 MinIO Object Key。"""

    validate_source_url(source_url)
    path_parts = [
        unquote(part)
        for part in urlsplit(source_url).path.split("/")
        if part
    ]

    try:
        product_images_index = path_parts.index("product-images")
        source_category = path_parts[product_images_index + 1]
        source_slug = path_parts[product_images_index + 2]
    except (ValueError, IndexError) as error:
        raise ValueError("无法从演示图片地址生成 Object Key") from error

    source_suffix = PurePosixPath(path_parts[-1]).suffix.lower()
    if source_suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("演示图片地址缺少受支持的扩展名")

    safe_category = re.sub(
        r"[^a-z0-9]+",
        "-",
        source_category.lower(),
    ).strip("-")
    safe_slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        source_slug.lower(),
    ).strip("-")
    normalized_suffix = ".jpg" if source_suffix == ".jpeg" else source_suffix

    if not safe_category or not safe_slug:
        raise ValueError("演示图片地址无法生成安全的 Object Key")

    return (
        f"{DEMO_OBJECT_PREFIX}/"
        f"{safe_category}/{safe_slug}{normalized_suffix}"
    )


def validate_downloaded_image(
    image_data: bytes,
    expected_suffix: str,
) -> str:
    """验证下载内容是真实图片，并返回上传用 Content-Type。"""

    if not image_data:
        raise ValueError("下载到的演示图片为空")
    if len(image_data) > MAX_IMAGE_SIZE:
        raise ValueError("演示图片超过 10 MiB")

    try:
        with Image.open(BytesIO(image_data)) as image:
            image_format = image.format
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ValueError("下载内容不是有效图片") from error

    if image_format not in IMAGE_FORMATS:
        raise ValueError("演示图片格式不受支持")

    content_type, actual_suffix = IMAGE_FORMATS[image_format]
    normalized_expected_suffix = (
        ".jpg" if expected_suffix == ".jpeg" else expected_suffix
    )
    if actual_suffix != normalized_expected_suffix:
        raise ValueError("演示图片实际格式与扩展名不一致")

    return content_type


def download_demo_image(source_url: str) -> tuple[bytes, str]:
    """下载并验真一张演示商品图片。"""

    validate_source_url(source_url)
    request = Request(
        source_url,
        headers={"User-Agent": "qingyu-mall-demo-import/1.0"},
    )

    try:
        with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            content_length = response.headers.get("Content-Length")
            if (
                content_length is not None
                and int(content_length) > MAX_IMAGE_SIZE
            ):
                raise ValueError("演示图片超过 10 MiB")

            image_data = response.read(MAX_IMAGE_SIZE + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise RuntimeError(
            f"下载演示图片失败：{source_url}"
        ) from error

    expected_suffix = PurePosixPath(
        urlsplit(source_url).path
    ).suffix.lower()
    content_type = validate_downloaded_image(
        image_data,
        expected_suffix,
    )
    return image_data, content_type


def minio_object_exists(client: Minio, object_name: str) -> bool:
    """检查对象是否存在；鉴权等其他错误继续抛出。"""

    try:
        client.stat_object(settings.minio_bucket, object_name)
    except S3Error as error:
        if error.code in MISSING_OBJECT_CODES:
            return False
        raise

    return True


def ensure_demo_object(
    client: Minio,
    source_url: str,
) -> tuple[str, bool]:
    """确保图片已进入 MinIO，返回公开地址和是否本次上传。"""

    object_name = build_demo_object_name(source_url)
    if minio_object_exists(client, object_name):
        return build_public_object_url(object_name), False

    image_data, content_type = download_demo_image(source_url)
    client.put_object(
        bucket_name=settings.minio_bucket,
        object_name=object_name,
        data=BytesIO(image_data),
        length=len(image_data),
        content_type=content_type,
    )
    return build_public_object_url(object_name), True


def classify_existing_product(
    products: list[Product],
    category_id: int,
    source_url: str,
    target_url: str,
) -> str:
    """判断已有记录是否属于这份演示清单。"""

    if not products:
        return "create"
    if len(products) != 1:
        return "conflict"

    product = products[0]
    if product.category_id != category_id:
        return "conflict"
    if product.image_url == target_url:
        return "managed"
    if product.image_url == source_url:
        return "migrate"
    return "conflict"


def seed_demo_products(*, dry_run: bool = False) -> SeedSummary:
    """把固定演示清单安全、幂等地同步到 MySQL 和 MinIO。"""

    summary = SeedSummary()
    changed_products: list[Product] = []
    demo_product_names = [spec["name"] for spec in PRODUCT_SPECS]
    if len(demo_product_names) != len(set(demo_product_names)):
        raise RuntimeError("演示商品清单中存在重复名称")

    minio_client = None
    if not dry_run:
        if not settings.minio_access_key or not settings.minio_secret_key:
            raise RuntimeError("MinIO 凭据未配置")

        minio_client = get_minio_client()
        if not minio_client.bucket_exists(settings.minio_bucket):
            raise RuntimeError(
                f"MinIO Bucket 不存在：{settings.minio_bucket}"
            )

    with Session(engine) as db:
        try:
            categories_by_name = {
                category.name: category
                for category in db.scalars(select(Category)).all()
            }

            for name, description in CATEGORY_SPECS.items():
                if name in categories_by_name:
                    continue

                summary.created_categories += 1
                if dry_run:
                    continue

                category = Category(name=name, description=description)
                db.add(category)
                db.flush()
                categories_by_name[name] = category

            existing_products_by_name: dict[str, list[Product]] = defaultdict(list)
            existing_products = db.scalars(
                select(Product).where(
                    Product.name.in_(demo_product_names),
                )
            ).all()
            for product in existing_products:
                existing_products_by_name[product.name].append(product)

            for product_spec in PRODUCT_SPECS:
                product_name = product_spec["name"]
                category = categories_by_name.get(product_spec["category"])
                source_url = product_spec["image_url"]
                object_name = build_demo_object_name(source_url)
                target_url = build_public_object_url(object_name)

                if category is None:
                    # 只有 dry-run 遇到缺失分类时会进入这里；此时同名记录
                    # 不能被安全认定为脚本数据。
                    if existing_products_by_name[product_name]:
                        summary.conflict_products += 1
                        summary.conflicts.append(product_name)
                    else:
                        summary.created_products += 1
                    continue

                action = classify_existing_product(
                    existing_products_by_name[product_name],
                    category.id,
                    source_url,
                    target_url,
                )

                if action == "conflict":
                    summary.conflict_products += 1
                    summary.conflicts.append(product_name)
                    continue
                if action == "create":
                    summary.created_products += 1
                elif action == "migrate":
                    summary.migrated_products += 1
                else:
                    summary.unchanged_products += 1

                if dry_run:
                    continue

                assert minio_client is not None
                image_url, uploaded = ensure_demo_object(
                    minio_client,
                    source_url,
                )
                if uploaded:
                    summary.uploaded_objects += 1
                else:
                    summary.reused_objects += 1

                if action == "managed":
                    continue
                if action == "migrate":
                    product = existing_products_by_name[product_name][0]
                    product.image_url = image_url
                    changed_products.append(product)
                    continue

                product_data = ProductCreate(
                    name=product_name,
                    price=Decimal(product_spec["price"]),
                    stock=product_spec["stock"],
                    description=product_spec["description"],
                    image_url=image_url,
                    category_id=category.id,
                )
                product = Product(**product_data.model_dump())
                db.add(product)
                changed_products.append(product)

            if dry_run:
                db.rollback()
                return summary

            db.flush()
            changed_product_ids = [product.id for product in changed_products]
            db.commit()

        except (SQLAlchemyError, S3Error, ValueError, RuntimeError, OSError):
            db.rollback()
            raise

    invalidate_product_cache(changed_product_ids)
    return summary


def format_summary(summary: SeedSummary, *, dry_run: bool) -> str:
    mode = "预览" if dry_run else "同步"
    lines = [
        f"演示商品{mode}完成：",
        f"  新增分类：{summary.created_categories}",
        f"  新增商品：{summary.created_products}",
        f"  迁移旧图片地址：{summary.migrated_products}",
        f"  已由 MinIO 管理：{summary.unchanged_products}",
        f"  同名冲突并跳过：{summary.conflict_products}",
    ]
    if not dry_run:
        lines.extend(
            [
                f"  上传 MinIO 对象：{summary.uploaded_objects}",
                f"  复用 MinIO 对象：{summary.reused_objects}",
            ]
        )
    if summary.conflicts:
        lines.append("  跳过商品：" + "、".join(summary.conflicts))
    return "\n".join(lines)


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只预览数据库动作，不下载图片或写入数据",
    )
    arguments = parser.parse_args()
    summary = seed_demo_products(dry_run=arguments.dry_run)
    print(format_summary(summary, dry_run=arguments.dry_run))


if __name__ == "__main__":
    main()
