from functools import lru_cache

from app.config import settings
from app.rag.providers.chat import DeepSeekChatProvider
from app.rag.providers.embedding import (
    LocalBgeEmbeddingProvider,
)


@lru_cache(maxsize=1)
def get_embedding_provider() -> LocalBgeEmbeddingProvider:
    """首次调用时加载并缓存本地 Embedding Provider。"""

    model_path = settings.rag_embedding_model_path

    if model_path is None:
        raise RuntimeError("未配置RAG Embedding模型路径")

    if not model_path.exists():
        raise RuntimeError(
            f"RAG Embedding模型目录不存在：{model_path}"
        )

    return LocalBgeEmbeddingProvider(
        model_path=model_path,
        dimension=settings.rag_embedding_dimension,
        device=settings.rag_embedding_device,
    )


@lru_cache(maxsize=1)
def get_chat_provider() -> DeepSeekChatProvider:
    """首次调用时创建并缓存 DeepSeek Provider。"""

    return DeepSeekChatProvider(
        api_key=(
            settings.deepseek_api_key.get_secret_value()
        ),
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout_seconds=(
            settings.deepseek_timeout_seconds
        ),
        max_tokens=settings.deepseek_max_tokens,
    )
