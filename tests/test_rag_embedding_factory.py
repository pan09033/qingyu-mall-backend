from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

from app.rag.providers import factory as factory_module


@pytest.fixture(autouse=True)
def clear_provider_caches():
    factory_module.get_embedding_provider.cache_clear()
    factory_module.get_chat_provider.cache_clear()
    yield
    factory_module.get_embedding_provider.cache_clear()
    factory_module.get_chat_provider.cache_clear()


def test_factory_creates_and_reuses_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    fake_provider = object()
    provider_constructor = Mock(return_value=fake_provider)

    monkeypatch.setattr(
        factory_module.settings,
        "rag_embedding_model_path",
        model_path,
    )
    monkeypatch.setattr(
        factory_module,
        "LocalBgeEmbeddingProvider",
        provider_constructor,
    )

    first_provider = factory_module.get_embedding_provider()
    second_provider = factory_module.get_embedding_provider()

    assert first_provider is fake_provider
    assert second_provider is first_provider
    provider_constructor.assert_called_once_with(
        model_path=model_path,
        dimension=512,
        device="cpu",
    )


def test_factory_rejects_missing_model_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        factory_module.settings,
        "rag_embedding_model_path",
        None,
    )

    with pytest.raises(
        RuntimeError,
        match="未配置RAG Embedding模型路径",
    ):
        factory_module.get_embedding_provider()


def test_factory_rejects_missing_model_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing-model"
    monkeypatch.setattr(
        factory_module.settings,
        "rag_embedding_model_path",
        missing_path,
    )

    with pytest.raises(
        RuntimeError,
        match="RAG Embedding模型目录不存在",
    ):
        factory_module.get_embedding_provider()


def test_factory_creates_and_reuses_chat_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_provider = object()
    provider_constructor = Mock(return_value=fake_provider)

    monkeypatch.setattr(
        factory_module.settings,
        "deepseek_api_key",
        SecretStr("test-api-key"),
    )
    monkeypatch.setattr(
        factory_module.settings,
        "deepseek_base_url",
        "https://api.deepseek.test",
    )
    monkeypatch.setattr(
        factory_module.settings,
        "deepseek_model",
        "test-model",
    )
    monkeypatch.setattr(
        factory_module.settings,
        "deepseek_timeout_seconds",
        12.0,
    )
    monkeypatch.setattr(
        factory_module.settings,
        "deepseek_max_tokens",
        256,
    )
    monkeypatch.setattr(
        factory_module,
        "DeepSeekChatProvider",
        provider_constructor,
    )

    first_provider = factory_module.get_chat_provider()
    second_provider = factory_module.get_chat_provider()

    assert first_provider is fake_provider
    assert second_provider is first_provider
    provider_constructor.assert_called_once_with(
        api_key="test-api-key",
        base_url="https://api.deepseek.test",
        model="test-model",
        timeout_seconds=12.0,
        max_tokens=256,
    )
