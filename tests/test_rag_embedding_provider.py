from pathlib import Path
from unittest.mock import Mock

import pytest

from app.rag.providers import embedding as embedding_module
from app.rag.providers.embedding import (
    QUERY_INSTRUCTION,
    LocalBgeEmbeddingProvider,
)


class FakeVector:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def tolist(self) -> list[float]:
        return self.values


def build_provider(
    monkeypatch: pytest.MonkeyPatch,
    actual_dimension: int = 512,
) -> tuple[LocalBgeEmbeddingProvider, Mock, Mock]:
    model = Mock()
    model.get_embedding_dimension.return_value = actual_dimension
    model_constructor = Mock(return_value=model)
    monkeypatch.setattr(
        embedding_module,
        "SentenceTransformer",
        model_constructor,
    )

    provider = LocalBgeEmbeddingProvider(
        Path("D:/models/bge-small-zh-v1.5"),
    )
    return provider, model, model_constructor


def test_provider_loads_local_cpu_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, model_constructor = build_provider(monkeypatch)

    model_constructor.assert_called_once_with(
        "D:\\models\\bge-small-zh-v1.5",
        device="cpu",
        local_files_only=True,
    )


def test_embed_documents_keeps_document_text_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, model, _ = build_provider(monkeypatch)
    model.encode.return_value = [
        FakeVector([0.1, 0.2]),
        FakeVector([0.3, 0.4]),
    ]
    texts = ["商品资料一", "商品资料二"]

    vectors = provider.embed_documents(texts)

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    model.encode.assert_called_once_with(
        texts,
        normalize_embeddings=True,
    )


def test_embed_documents_skips_model_for_empty_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, model, _ = build_provider(monkeypatch)

    assert provider.embed_documents([]) == []
    model.encode.assert_not_called()


def test_embed_query_adds_retrieval_instruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, model, _ = build_provider(monkeypatch)
    model.encode.return_value = FakeVector([0.5, 0.6])

    vector = provider.embed_query("什么耳机适合办公？")

    assert vector == [0.5, 0.6]
    model.encode.assert_called_once_with(
        QUERY_INSTRUCTION + "什么耳机适合办公？",
        normalize_embeddings=True,
    )


def test_provider_rejects_unexpected_model_dimension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(
        RuntimeError,
        match="预期512，实际384",
    ):
        build_provider(
            monkeypatch,
            actual_dimension=384,
        )
