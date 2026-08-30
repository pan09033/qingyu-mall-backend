import redis

from app.config import settings


redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password,
    protocol=settings.redis_protocol,
    decode_responses=True,
    socket_connect_timeout=(
        settings.redis_connect_timeout_seconds
    ),
    socket_timeout=(
        settings.redis_socket_timeout_seconds
    ),
)
