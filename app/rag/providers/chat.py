import httpx



class ChatProviderError(RuntimeError):
    """调用大模型服务失败。"""


class ChatProviderUnavailableError(ChatProviderError):
    """大模型服务暂时不可用。"""


class ChatProviderResponseError(ChatProviderError):
    """大模型返回了无法使用的数据。"""

class DeepSeekChatProvider:
    """通过 DeepSeek API 生成商城问答内容。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
    ) -> None:
        if not api_key.strip():
            raise ValueError("DeepSeek API Key不能为空")

        self._model = model
        self._max_tokens = max_tokens
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
        )

    def generate_answer(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """根据系统规则和用户提示生成回答。"""
        try:
            response = self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                    "thinking": {
                        "type": "disabled",
                    },
                    "max_tokens": self._max_tokens,
                    "stream": False,
                },
            )

            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise ChatProviderUnavailableError(
                "DeepSeek服务响应超时"
            ) from error
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code

            if status_code in {401, 403}:
                message = "DeepSeek服务认证失败"
            elif status_code == 429:
                message = "DeepSeek请求过于频繁"
            else:
                message = "DeepSeek服务暂时不可用"

            raise ChatProviderUnavailableError(
                message
            ) from error
        except httpx.RequestError as error:
            raise ChatProviderUnavailableError(
                "无法连接DeepSeek服务"
            ) from error
        try:
            response_data = response.json()
        except ValueError as error:
            raise ChatProviderResponseError(
                "DeepSeek返回的不是有效JSON"
            ) from error

        try:
            answer = response_data[
                "choices"
            ][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ChatProviderResponseError(
                "DeepSeek返回格式无效"
            ) from error

        if not isinstance(answer, str) or not answer.strip():
            raise ChatProviderResponseError("DeepSeek返回了空回答")

        return answer.strip()
