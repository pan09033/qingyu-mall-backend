from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

from app.config import settings


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = (
    WORKSPACE_ROOT
    / "local_embedding"
    / "bge-small-zh-v1.5"
)

QUERY_INSTRUCTION = (
    "为这个句子生成表示以用于检索相关文章："
)

PRODUCTS = [
    (
        1,
        "静音降噪蓝牙耳机，价格399元，适合办公室和通勤使用。",
    ),
    (
        2,
        "青轴机械键盘，价格459元，按键声音清脆，适合游戏。",
    ),
    (
        3,
        "家用蓝牙音箱，价格299元，适合客厅播放音乐。",
    ),
]


def search_products(question: str) -> None:
    model = SentenceTransformer(
        str(MODEL_PATH),
        device="cpu",
        local_files_only=True,
    )

    product_texts = [content for _, content in PRODUCTS]

    product_vectors = model.encode(
        product_texts,
        normalize_embeddings=True,
    )
    question_vector = model.encode(
        QUERY_INSTRUCTION + question,
        normalize_embeddings=True,
    )

    with psycopg.connect(
        host=settings.rag_db_host,
        port=settings.rag_db_port,
        dbname=settings.rag_db_name,
        user=settings.rag_db_user,
        password=settings.rag_db_password.get_secret_value(),
        connect_timeout=settings.rag_db_connect_timeout_seconds,
    ) as connection:
        register_vector(connection)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TEMP TABLE rag_practice_products (
                    product_id INTEGER PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding VECTOR(512) NOT NULL
                )
                """
            )

            rows = [
                (product_id, content, vector)
                for (product_id, content), vector
                in zip(PRODUCTS, product_vectors, strict=True)
            ]

            cursor.executemany(
                """
                INSERT INTO rag_practice_products (
                    product_id,
                    content,
                    embedding
                )
                VALUES (%s, %s, %s)
                """,
                rows,
            )

            cursor.execute(
                """
                SELECT
                    product_id,
                    content,
                    1 - (embedding <=> %s) AS similarity
                FROM rag_practice_products
                ORDER BY embedding <=> %s
                """,
                (question_vector, question_vector),
            )

            results = cursor.fetchall()

    embedding_dimension = model.get_embedding_dimension()

    if embedding_dimension != 512:
        raise RuntimeError(
            f"Embedding 维度错误：预期512，实际{embedding_dimension}"
        )

    for product_id, content, similarity in results:
        print(
            f"商品 {product_id}，"
            f"相似度 {similarity:.3f}：{content}"
        )


if __name__ == "__main__":
    search_products("预算500元以内，适合安静办公的商品")