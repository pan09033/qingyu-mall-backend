from unittest.mock import patch

import httpx
import pytest

from app.rag.providers.chat import (
    ChatProviderResponseError,
    ChatProviderUnavailableError,
    DeepSeekChatProvider,
)


def test_chat_provider_builds_configured_http_client() -> None:
    with patch(
        "app.rag.providers.chat.httpx.Client",
    ) as client_class:
        provider = DeepSeekChatProvider(
            api_key="test-api-key",
            base_url="https://api.deepseek.com/",
            model="deepseek-flash",
            timeout_seconds=30.0,
            max_tokens=512,
        )

    client_class.assert_called_once_with(
        base_url="https://api.deepseek.com",
        headers={
            "Authorization": "Bearer test-api-key",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    assert provider._model == "deepseek-flash"
    assert provider._max_tokens == 512


def test_chat_provider_rejects_blank_api_key() -> None:
    with patch(
        "app.rag.providers.chat.httpx.Client",
    ) as client_class:
        with pytest.raises(
            ValueError,
            match="DeepSeek API Key不能为空",
        ):
            DeepSeekChatProvider(
                api_key="   ",
                base_url="https://api.deepseek.com",
                model="deepseek-flash",
                timeout_seconds=30.0,
                max_tokens=512,
            )

    client_class.assert_not_called()


def test_generate_answer_sends_prompts_and_returns_content() -> None:
    with patch(
        "app.rag.providers.chat.httpx.Client",
    ) as client_class:
        provider = DeepSeekChatProvider(
            api_key="test-api-key",
            base_url="https://api.deepseek.com",
            model="deepseek-flash",
            timeout_seconds=30.0,
            max_tokens=512,
        )
        response = client_class.return_value.post.return_value
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "  可以申请退货退款。  ",
                    },
                },
            ],
        }

        answer = provider.generate_answer(
            "只能根据商城资料回答。",
            "用户问题：已发货后怎样退款？",
        )

    client_class.return_value.post.assert_called_once_with(
        "/chat/completions",
        json={
            "model": "deepseek-flash",
            "messages": [
                {
                    "role": "system",
                    "content": "只能根据商城资料回答。",
                },
                {
                    "role": "user",
                    "content": "用户问题：已发货后怎样退款？",
                },
            ],
            "thinking": {
                "type": "disabled",
            },
            "max_tokens": 512,
            "stream": False,
        },
    )
    response.raise_for_status.assert_called_once_with()
    assert answer == "可以申请退货退款。"


def test_generate_answer_rejects_invalid_response_shape() -> None:
    with patch(
        "app.rag.providers.chat.httpx.Client",
    ) as client_class:
        provider = DeepSeekChatProvider(
            api_key="test-api-key",
            base_url="https://api.deepseek.com",
            model="deepseek-flash",
            timeout_seconds=30.0,
            max_tokens=512,
        )
        client_class.return_value.post.return_value.json.return_value = {
            "choices": [],
        }

        with pytest.raises(
            ChatProviderResponseError,
            match="DeepSeek返回格式无效",
        ):
            provider.generate_answer("系统规则", "用户提示")


def test_generate_answer_rejects_blank_content() -> None:
    with patch(
        "app.rag.providers.chat.httpx.Client",
    ) as client_class:
        provider = DeepSeekChatProvider(
            api_key="test-api-key",
            base_url="https://api.deepseek.com",
            model="deepseek-flash",
            timeout_seconds=30.0,
            max_tokens=512,
        )
        client_class.return_value.post.return_value.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "   ",
                    },
                },
            ],
        }

        with pytest.raises(
            ChatProviderResponseError,
            match="DeepSeek返回了空回答",
        ):
            provider.generate_answer("系统规则", "用户提示")


def test_generate_answer_translates_timeout() -> None:
    request = httpx.Request(
        "POST",
        "https://api.deepseek.com/chat/completions",
    )

    with patch(
        "app.rag.providers.chat.httpx.Client",
    ) as client_class:
        provider = DeepSeekChatProvider(
            api_key="test-api-key",
            base_url="https://api.deepseek.com",
            model="deepseek-flash",
            timeout_seconds=30.0,
            max_tokens=512,
        )
        client_class.return_value.post.side_effect = httpx.ReadTimeout(
            "timed out",
            request=request,
        )

        with pytest.raises(
            ChatProviderUnavailableError,
            match="DeepSeek服务响应超时",
        ):
            provider.generate_answer("系统规则", "用户提示")


@pytest.mark.parametrize(
    ("status_code", "error_message"),
    [
        (401, "DeepSeek服务认证失败"),
        (403, "DeepSeek服务认证失败"),
        (429, "DeepSeek请求过于频繁"),
        (500, "DeepSeek服务暂时不可用"),
    ],
)
def test_generate_answer_translates_http_status(
    status_code: int,
    error_message: str,
) -> None:
    request = httpx.Request(
        "POST",
        "https://api.deepseek.com/chat/completions",
    )
    response = httpx.Response(
        status_code,
        request=request,
    )

    with patch(
        "app.rag.providers.chat.httpx.Client",
    ) as client_class:
        provider = DeepSeekChatProvider(
            api_key="test-api-key",
            base_url="https://api.deepseek.com",
            model="deepseek-flash",
            timeout_seconds=30.0,
            max_tokens=512,
        )
        client_class.return_value.post.return_value = response

        with pytest.raises(
            ChatProviderUnavailableError,
            match=error_message,
        ):
            provider.generate_answer("系统规则", "用户提示")


def test_generate_answer_translates_connection_error() -> None:
    request = httpx.Request(
        "POST",
        "https://api.deepseek.com/chat/completions",
    )

    with patch(
        "app.rag.providers.chat.httpx.Client",
    ) as client_class:
        provider = DeepSeekChatProvider(
            api_key="test-api-key",
            base_url="https://api.deepseek.com",
            model="deepseek-flash",
            timeout_seconds=30.0,
            max_tokens=512,
        )
        client_class.return_value.post.side_effect = httpx.ConnectError(
            "connection failed",
            request=request,
        )

        with pytest.raises(
            ChatProviderUnavailableError,
            match="无法连接DeepSeek服务",
        ):
            provider.generate_answer("系统规则", "用户提示")


def test_generate_answer_rejects_invalid_json() -> None:
    with patch(
        "app.rag.providers.chat.httpx.Client",
    ) as client_class:
        provider = DeepSeekChatProvider(
            api_key="test-api-key",
            base_url="https://api.deepseek.com",
            model="deepseek-flash",
            timeout_seconds=30.0,
            max_tokens=512,
        )
        response = client_class.return_value.post.return_value
        response.json.side_effect = ValueError("invalid json")

        with pytest.raises(
            ChatProviderResponseError,
            match="DeepSeek返回的不是有效JSON",
        ):
            provider.generate_answer("系统规则", "用户提示")
