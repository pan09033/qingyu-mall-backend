import psycopg

from app.config import settings


def check_rag_database_connection() -> None:
    with psycopg.connect(
        host=settings.rag_db_host,
        port=settings.rag_db_port,
        dbname=settings.rag_db_name,
        user=settings.rag_db_user,
        password=settings.rag_db_password.get_secret_value(),
        connect_timeout=settings.rag_db_connect_timeout_seconds,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    current_database(),
                    current_user,
                    extversion
                FROM pg_extension
                WHERE extname = 'vector'
                """
            )
            result = cursor.fetchone()

    if result is None:
        raise RuntimeError("当前数据库没有安装 vector 扩展")

    database_name, database_user, vector_version = result

    print(f"database={database_name}")
    print(f"user={database_user}")
    print(f"vector_extension={vector_version}")


if __name__ == "__main__":
    check_rag_database_connection()