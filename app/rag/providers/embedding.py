from pathlib import Path
from typing import Literal

from sentence_transformers import SentenceTransformer


QUERY_INSTRUCTION = (
    "为这个句子生成表示以用于检索相关文章："
)


class LocalBgeEmbeddingProvider:
    """使用本地 BGE 模型生成资料向量和问题向量。"""

    def __init__(
        self,
        model_path: Path,
        dimension: int = 512,
        device: Literal["cpu", "cuda"] = "cpu",
    ) -> None:
        self._model = SentenceTransformer(
            str(model_path),
            device=device,
            local_files_only=True,
        )
        self._dimension = dimension

        actual_dimension = self._model.get_embedding_dimension()

        if actual_dimension != dimension:
            raise RuntimeError(
                "Embedding维度不匹配："
                f"预期{dimension}，实际{actual_dimension}"
            )

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """生成知识资料向量。"""

        if not texts:
            return []

        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
        )

        return [
            vector.tolist()
            for vector in vectors
        ]

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """生成用户问题向量。"""

        query_text = QUERY_INSTRUCTION + text

        vector = self._model.encode(
            query_text,
            normalize_embeddings=True,
        )

        return vector.tolist()