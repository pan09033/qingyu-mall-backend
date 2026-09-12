import json

from app.config import settings
from app.storage import get_minio_client


def main() -> None:
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": ["s3:GetObject"],
                "Resource": [
                    (
                        f"arn:aws:s3:::"
                        f"{settings.minio_bucket}/products/*"
                    )
                ],
            }
        ],
    }

    client = get_minio_client()
    client.set_bucket_policy(
        bucket_name=settings.minio_bucket,
        policy=json.dumps(policy),
    )

    print("商品图片匿名只读策略设置成功")


if __name__ == "__main__":
    main()